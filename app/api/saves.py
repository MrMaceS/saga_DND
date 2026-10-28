"""Сохранения. Управляет только Стол (токен Стола); игроки видят лишь индикатор."""
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import table_token_from
from app.db.engine import get_session
from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.engine import saves
from app.services import savegame
from app.services.sync import push_states, session_lock

router = APIRouter(prefix="/api", tags=["saves"])


class LoadBody(BaseModel):
    slot_id: int


@router.get("/saves/{code}")
async def list_saves(code: str, table_token: str = Depends(table_token_from), db: AsyncSession = Depends(get_session)):
    session = await SessionRepository(db).require_table(code, table_token)
    return await savegame.list_slots(db, session["id"])


@router.post("/saves/{code}/manual")
async def manual_save(code: str, table_token: str = Depends(table_token_from), db: AsyncSession = Depends(get_session)):
    session = await SessionRepository(db).require_table(code, table_token)
    if session["status"] != "playing":
        raise SagaError("invalid_state")
    async with session_lock(session["id"]):
        slot_id = await savegame.manual_save(db, session["id"])
    return {"slot_id": slot_id}


@router.post("/saves/{code}/load")
async def load_save(code: str, body: LoadBody, table_token: str = Depends(table_token_from),
                    db: AsyncSession = Depends(get_session)):
    """Загрузка возможна только пока вечер не идёт (пауза, лобби, конец): откатов посреди игры нет."""
    session = await SessionRepository(db).require_table(code, table_token)
    if session["status"] == "playing":
        raise SagaError("invalid_state", "Откат посреди игры невозможен: цена решений должна сохраняться")
    async with session_lock(session["id"]):
        await savegame.load_slot(db, session["id"], body.slot_id)
    await push_states(db, session["id"])
    return {"loaded": body.slot_id}


@router.get("/saves/{code}/export/{slot_id}")
async def export_save(code: str, slot_id: int, table_token: str = Depends(table_token_from),
                      db: AsyncSession = Depends(get_session)):
    session = await SessionRepository(db).require_table(code, table_token)
    res = await db.execute(text("SELECT snapshot_json FROM save_slot WHERE id = :i AND session_id = :s"),
                           {"i": slot_id, "s": session["id"]})
    row = res.fetchone()
    if not row:
        raise SagaError("not_found", "Сохранение не найдено")
    return json.loads(row.snapshot_json)


@router.post("/saves/{code}/import")
async def import_save(code: str, snapshot: dict, table_token: str = Depends(table_token_from),
                      db: AsyncSession = Depends(get_session)):
    session = await SessionRepository(db).require_table(code, table_token)
    if session["status"] == "playing":
        raise SagaError("invalid_state", "Импорт возможен только вне активного вечера")
    async with session_lock(session["id"]):
        await saves.apply_snapshot(session["id"], snapshot, db)
    await push_states(db, session["id"])
    return {"imported": True}
