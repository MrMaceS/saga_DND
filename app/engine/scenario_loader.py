"""Инициализация мира в БД из YAML-сценария (никаких захардкоженных идентификаторов)."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import SagaError
from app.engine import content
from app.engine.scene import ScenarioValidationError


async def initialize_scenario(db: AsyncSession, session_id: str, story_id: str,
                              players: list[dict[str, Any]]) -> dict[str, Any]:
    """Создаёт locations, zone_state, tasks, clocks, npc, hero_state и стартовые факты.

    players: [{"hero_id": ..., "player_name": ...}]. Возвращает загруженный сценарий.
    """
    try:
        data = content.get_scenario(story_id)
    except FileNotFoundError:
        raise SagaError("story_unavailable")
    except ScenarioValidationError as e:
        raise SagaError("story_unavailable", f"Ошибка сценария: {e}")

    heroes = content.heroes_catalog()
    zone_loc = content.zone_to_location(data)
    start_zone = data["start_zone"]
    start_loc = zone_loc[start_zone]

    for loc_id in data["locations"]:
        await db.execute(text("INSERT INTO location (session_id, id, discovered, visited_by_any) "
                              "VALUES (:s, :id, 0, 0)"), {"s": session_id, "id": loc_id})
    for zone in zone_loc:
        await db.execute(text("INSERT INTO zone_state (session_id, zone_id, visited) VALUES (:s, :z, 0)"),
                         {"s": session_id, "z": zone})

    for task in data["tasks"]:
        await db.execute(
            text("INSERT INTO task (session_id, id, location_id, zone_id, title, status, world_truth_json, "
                 "consequence_if_ignored, public_level) VALUES (:s, :id, :loc, :zone, :title, 'open', "
                 ":truth, :cons, :pub)"),
            {"s": session_id, "id": task["id"], "loc": zone_loc[task["zone"]], "zone": task["zone"],
             "title": task["title"], "truth": json.dumps(task["levels"], ensure_ascii=False),
             "cons": task.get("ignored_clock") or "none", "pub": task.get("public_start_level", 0)})

    for clock in data["clocks"]:
        await db.execute(
            text("INSERT INTO clock (session_id, id, location_id, segments, filled) "
                 "VALUES (:s, :id, :loc, :seg, :filled)"),
            {"s": session_id, "id": clock["id"], "loc": clock["location"],
             "seg": clock["segments"], "filled": clock["start"]})

    for npc in data.get("npcs", []):
        await db.execute(
            text("INSERT INTO npc (session_id, id, name, attitude, state_json) VALUES (:s, :id, :n, :a, :st)"),
            {"s": session_id, "id": npc["id"], "n": npc["name"], "a": npc["attitude"],
             "st": json.dumps({"zone": npc["zone"], "state": npc["state"]}, ensure_ascii=False)})

    hero_ids = [p["hero_id"] for p in players]
    for pl in players:
        h = heroes[pl["hero_id"]]
        await db.execute(
            text("INSERT INTO hero_state (session_id, hero_id, stats_json, endurance, fate, location_id, zone_id, "
                 "abilities_json, inventory_json, secrets_json, goal_progress) VALUES (:s, :h, :stats, :end, "
                 ":fate, :loc, :zone, :ab, :inv, :sec, 0)"),
            {"s": session_id, "h": h["id"], "stats": json.dumps(h["stats"]), "end": h["endurance"],
             "fate": 1, "loc": start_loc, "zone": start_zone,
             "ab": json.dumps({"minor_ready": True}), "inv": json.dumps(h["start_items"], ensure_ascii=False),
             "sec": json.dumps({"story": "sealed", "personal": "known"})})
        await db.execute(text("INSERT OR IGNORE INTO hero_zone_visit (session_id, hero_id, zone_id) "
                              "VALUES (:s, :h, :z)"), {"s": session_id, "h": h["id"], "z": start_zone})

    await db.execute(text("UPDATE zone_state SET visited = 1 WHERE session_id = :s AND zone_id = :z"),
                     {"s": session_id, "z": start_zone})
    # Часы угроз запускаются при первом входе героя в локацию (правило из дизайна).
    await db.execute(text("UPDATE location SET visited_by_any = 1, discovered = 1 "
                          "WHERE session_id = :s AND id = :l"), {"s": session_id, "l": start_loc})

    # Явления, которые диктор описывает в открывающей кат-сцене, известны всем на уровне 1.
    for task in data["tasks"]:
        for level in range(1, task.get("public_start_level", 0) + 1):
            await add_fact(db, session_id, f"task:{task['id']}:{level}", task["levels"][level], level,
                           "narrator", 0, hero_ids)
    return data


async def add_fact(db: AsyncSession, session_id: str, fact_id: str, fact_text: str, level: int,
                   source: str, round_no: int, known_by: list[str]) -> None:
    await db.execute(
        text("INSERT OR IGNORE INTO fact (session_id, id, text, level, source, round_no) "
             "VALUES (:s, :id, :t, :l, :src, :r)"),
        {"s": session_id, "id": fact_id, "t": fact_text, "l": level, "src": source, "r": round_no})
    for hero in known_by:
        await db.execute(text("INSERT OR IGNORE INTO fact_known_by (session_id, fact_id, hero_id) "
                              "VALUES (:s, :f, :h)"), {"s": session_id, "f": fact_id, "h": hero})
