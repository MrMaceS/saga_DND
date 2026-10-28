import secrets
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import table_token_from
from app.db.engine import get_session
from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.services import rounds, state, votes, world
from app.services.sync import push_states, session_lock
from app.ws.hub import hub

router = APIRouter(prefix="/api", tags=["sessions"])


class CreateSession(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    story_id: str
    player_count: int = Field(ge=2, le=10)


class JoinBody(BaseModel):
    player_name: str = Field(min_length=1, max_length=30)


class ClaimBody(BaseModel):
    hero_id: str
    device_token: str


class TokenBody(BaseModel):
    device_token: str


class ReadyBody(BaseModel):
    device_token: str
    is_ready: bool = True


@router.post("/sessions")
async def create_session(body: CreateSession, db: AsyncSession = Depends(get_session)):
    created = await SessionRepository(db).create_session(body.name, body.story_id, body.player_count)
    return {**created, "status": "lobby", "story_id": body.story_id, "player_count": body.player_count}


@router.get("/sessions/resumable")
async def resumable(db: AsyncSession = Depends(get_session)):
    """Для «Продолжить сагу» на Столе: сессии, у которых уже есть сохранения."""
    return await world.rows(
        db, "SELECT g.join_code AS code, g.name, g.story_id, g.status, g.round_no, g.evening_no, "
            "(SELECT COUNT(*) FROM player_binding p WHERE p.session_id = g.id) AS players, "
            "(SELECT MAX(created_at) FROM save_slot s WHERE s.session_id = g.id) AS last_save "
            "FROM game_session g WHERE g.status IN ('playing','paused') "
            "AND EXISTS (SELECT 1 FROM save_slot s WHERE s.session_id = g.id) ORDER BY g.rowid DESC LIMIT 20")


@router.get("/sessions/{code}")
async def get_lobby(code: str, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    players = await repo.players(session["id"])
    return {"code": session["join_code"], "name": session["name"], "status": session["status"],
            "story_id": session["story_id"], "player_count": session["player_count"],
            "lobby": state.lobby_block(session, players)}


@router.post("/sessions/{code}/join")
async def join(code: str, body: JoinBody, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    async with session_lock(session["id"]):
        token = await repo.join_session(session, body.player_name)
    await push_states(db, session["id"])
    return {"device_token": token, "status": session["status"]}


@router.post("/sessions/{code}/claim")
async def claim(code: str, body: ClaimBody, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    async with session_lock(session["id"]):
        await repo.claim_hero(session, body.hero_id, body.device_token)
    hub.set_hero(body.device_token, body.hero_id)
    await push_states(db, session["id"])
    return {"hero_id": body.hero_id}


@router.post("/sessions/{code}/ready")
async def ready(code: str, body: ReadyBody, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    await repo.set_ready(session, body.device_token, body.is_ready)
    await push_states(db, session["id"])
    return {"ready": body.is_ready}


@router.post("/sessions/{code}/oath")
async def oath(code: str, body: TokenBody, db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    await repo.set_oath(session, body.device_token)
    await push_states(db, session["id"])
    return {"sworn": True}


@router.post("/sessions/{code}/start")
async def start(code: str, table_token: str = Depends(table_token_from), db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_table(code, table_token)
    async with session_lock(session["id"]):
        await rounds.start_session(db, session)
    return {"status": "playing"}


@router.post("/sessions/{code}/exit")
async def request_exit(code: str, table_token: str = Depends(table_token_from), db: AsyncSession = Depends(get_session)):
    """«Сохранить и выйти»: сохранение произойдёт, только когда согласятся все."""
    session = await SessionRepository(db).require_table(code, table_token)
    if session["status"] != "playing":
        raise SagaError("invalid_state")
    await votes.start_exit_vote(db, session)
    return {"requested": True}


@router.post("/sessions/{code}/resume")
async def resume(code: str, db: AsyncSession = Depends(get_session)):
    """Стол продолжает сохранённую сагу: выдаётся новый токен Стола, игроки возвращаются по своим токенам."""
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    if session["status"] not in ("paused", "playing"):
        raise SagaError("invalid_state", "Эту сагу нельзя продолжить")
    new_token = secrets.token_hex(16)
    await db.execute(text("UPDATE game_session SET table_token = :t, status = 'playing', round_phase = 'declaring' "
                          "WHERE id = :s"), {"t": new_token, "s": session["id"]})
    await db.execute(text("UPDATE player_binding SET status = 'away' WHERE session_id = :s"), {"s": session["id"]})
    await db.commit()
    return {"table_token": new_token, "join_code": session["join_code"]}
