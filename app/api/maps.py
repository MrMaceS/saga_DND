"""Карты. Имена зон отдаются только посещённым; часы только те, о которых что-то известно."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import table_token_from
from app.db.engine import get_session
from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.engine import map_state
from app.services import state, world

router = APIRouter(prefix="/api", tags=["maps"])


def _require_started(session: dict) -> None:
    if session["status"] not in ("playing", "paused", "finished"):
        raise SagaError("invalid_state", "Сага ещё не началась: карты нет")


@router.get("/maps/{code}/table")
async def table_map(code: str, table_token: str = Depends(table_token_from), db: AsyncSession = Depends(get_session)):
    """{ zones: [{id, name, visited, ...}], adjacency, clocks: [{id, location_id, filled, segments, ...}] }"""
    session = await SessionRepository(db).require_table(code, table_token)
    _require_started(session)
    return await state.build_table_map_payload(db, session)


@router.get("/maps/{code}/hand")
async def hand_map(code: str, device_token: str = Query(...), db: AsyncSession = Depends(get_session)):
    """{ hero_id, zones: [{id, name, visible, visited}], adjacency, current_zone }"""
    repo = SessionRepository(db)
    session = await repo.require_session(code)
    player = await repo.require_player(session["id"], device_token)
    _require_started(session)
    if not player["hero_id"]:
        raise SagaError("forbidden", "У вас нет героя")
    scenario = world.scenario_of(session)
    hs = await world.hero_row(db, session["id"], player["hero_id"])
    levels = await world.hero_task_levels(db, session["id"], player["hero_id"])
    visited = await world.visited_zones_hero(db, session["id"], player["hero_id"])
    here = [h["hero_id"] for h in await world.all_hero_rows(db, session["id"])
            if h["zone_id"] == hs["zone_id"] and h["hero_id"] != player["hero_id"]]
    task_zones = {t["zone"] for t in scenario["tasks"] if levels.get(t["id"], 0) >= 1}
    return map_state.build_personal_map(scenario, player["hero_id"], visited, hs["zone_id"], here, task_zones)
