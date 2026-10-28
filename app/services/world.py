"""Чтение состояния мира из БД (общие запросы для сервисов)."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import content
from engine import rules


async def rows(db: AsyncSession, sql: str, **params: Any) -> list[dict[str, Any]]:
    res = await db.execute(text(sql), params)
    return [dict(r._mapping) for r in res.fetchall()]


async def row(db: AsyncSession, sql: str, **params: Any) -> dict[str, Any] | None:
    found = await rows(db, sql, **params)
    return found[0] if found else None


async def hero_row(db: AsyncSession, sid: str, hero_id: str) -> dict[str, Any] | None:
    r = await row(db, "SELECT * FROM hero_state WHERE session_id = :s AND hero_id = :h", s=sid, h=hero_id)
    if not r:
        return None
    r["stats"] = json.loads(r["stats_json"])
    r["abilities"] = json.loads(r["abilities_json"])
    r["inventory"] = json.loads(r["inventory_json"])
    r["secrets"] = json.loads(r["secrets_json"])
    return r


async def all_hero_rows(db: AsyncSession, sid: str) -> list[dict[str, Any]]:
    ids = [r["hero_id"] for r in await rows(db, "SELECT hero_id FROM hero_state WHERE session_id = :s ORDER BY rowid", s=sid)]
    return [await hero_row(db, sid, h) for h in ids]


async def wounds(db: AsyncSession, sid: str, hero_id: str) -> list[dict[str, Any]]:
    return await rows(db, "SELECT * FROM injury WHERE session_id = :s AND hero_id = :h ORDER BY id", s=sid, h=hero_id)


def wound_objects(wound_rows: list[dict[str, Any]]) -> list[rules.Wound]:
    return [rules.Wound(rules.Severity(w["severity"]), rules.BodyPart(w["body_part"])) for w in wound_rows]


async def visited_zones_global(db: AsyncSession, sid: str) -> set[str]:
    return {r["zone_id"] for r in await rows(db, "SELECT zone_id FROM zone_state WHERE session_id = :s AND visited = 1", s=sid)}


async def visited_zones_hero(db: AsyncSession, sid: str, hero_id: str) -> set[str]:
    return {r["zone_id"] for r in await rows(
        db, "SELECT zone_id FROM hero_zone_visit WHERE session_id = :s AND hero_id = :h", s=sid, h=hero_id)}


async def active_locations(db: AsyncSession, sid: str) -> set[str]:
    return {r["id"] for r in await rows(db, "SELECT id FROM location WHERE session_id = :s AND visited_by_any = 1", s=sid)}


async def clock_rows(db: AsyncSession, sid: str) -> list[dict[str, Any]]:
    return await rows(db, "SELECT id, location_id, filled, segments, resolved FROM clock WHERE session_id = :s ORDER BY rowid", s=sid)


async def task_public_levels(db: AsyncSession, sid: str) -> dict[str, int]:
    return {r["id"]: r["public_level"] for r in await rows(db, "SELECT id, public_level FROM task WHERE session_id = :s", s=sid)}


async def facts_of_hero(db: AsyncSession, sid: str, hero_id: str) -> list[dict[str, Any]]:
    return await rows(
        db, "SELECT f.id, f.text, f.level, f.source, f.round_no FROM fact f JOIN fact_known_by k "
            "ON k.session_id = f.session_id AND k.fact_id = f.id WHERE f.session_id = :s AND k.hero_id = :h "
            "ORDER BY f.round_no, f.rowid", s=sid, h=hero_id)


async def hero_task_levels(db: AsyncSession, sid: str, hero_id: str) -> dict[str, int]:
    levels: dict[str, int] = {}
    for f in await facts_of_hero(db, sid, hero_id):
        parts = f["id"].split(":")
        if parts[0] == "task" and len(parts) == 3:
            levels[parts[1]] = max(levels.get(parts[1], 0), int(parts[2]))
    return levels


def scenario_of(session: dict[str, Any]) -> dict[str, Any]:
    return content.get_scenario(session["story_id"])


def settings_of(session: dict[str, Any]) -> dict[str, Any]:
    return json.loads(session["settings_json"])
