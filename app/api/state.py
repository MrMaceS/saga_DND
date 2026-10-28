"""Полное состояние (для первой загрузки страницы и как запасной канал при обрыве WebSocket)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import table_token_from
from app.db.engine import get_session
from app.db.repositories import SessionRepository
from app.services import state

router = APIRouter(prefix="/api", tags=["state"])


@router.get("/table/{code}")
async def table_state(code: str, table_token: str = Depends(table_token_from), db: AsyncSession = Depends(get_session)):
    session = await SessionRepository(db).require_table(code, table_token)
    return await state.build_table_state(db, session)


@router.get("/hand/{code}")
async def hand_state(code: str, device_token: str = Query(...), db: AsyncSession = Depends(get_session)):
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    player = await repo.require_player(session["id"], device_token)
    return await state.build_hand_state(db, session, player)
