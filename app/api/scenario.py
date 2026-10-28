from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.engine import get_session
from app.db.repositories import SessionRepository
from app.engine.scenario_loader import initialize_scenario, process_end_of_round
from app.domain.errors import SagaError

router = APIRouter(prefix="/api", tags=["scenario"])


@router.post("/sessions/{code}/start")
async def start_scenario(code: str, db_session: AsyncSession = Depends(get_session)):
    """Переводит сессию в статус playing и инициализирует сценарий."""
    repo = SessionRepository(db_session)
    session_data = await repo.get_session_by_code(code)
    if not session_data:
        raise SagaError("forbidden", "Сессия не найдена").to_http_exception()

    if session_data["status"] not in ("lobby", "hero_select", "oath"):
        raise SagaError("invalid_state", "Сессия уже началась").to_http_exception()

    await initialize_scenario(session_data["id"], session_data["story_id"], db_session)

    await db_session.execute(
        text("UPDATE game_session SET status = 'playing', round_no = 1 WHERE join_code = :code"),
        {"code": code}
    )
    await db_session.commit()

    return {"status": "ok", "message": "Сцена начата"}


@router.post("/sessions/{code}/next_round")
async def next_round(code: str, db_session: AsyncSession = Depends(get_session)):
    """
    Завершает текущий раунд, тикает часы, триггерит кат-сцены, начинает новый.
    """
    repo = SessionRepository(db_session)
    session_data = await repo.get_session_by_code(code)
    if not session_data or session_data["status"] != "playing":
        raise SagaError("invalid_state").to_http_exception()

    # Эмуляция активных локаций (в реальной игре берётся из состояния мира)
    active_locations = {"ship", "shore"}

    triggered = await process_end_of_round(session_data["id"], active_locations, db_session)

    # Увеличиваем номер раунда
    new_round_no = session_data["round_no"] + 1
    await db_session.execute(
        text("UPDATE game_session SET round_no = :new_round WHERE join_code = :code"),
        {"code": code, "new_round": new_round_no}
    )
    await db_session.commit()

    return {"status": "ok", "new_round": new_round_no, "triggered_cutscenes": triggered}