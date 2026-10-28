"""Построение состояний для Стола и для руки каждого игрока. Клиент получает только то, что знает его герой."""
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import SessionRepository
from app.engine import content, map_state
from app.services import world
from engine import rules

FEED_TYPES = ("narration.public", "feed.message")
SIMPLE_CHIPS = ["Осмотреться", "Прислушаться", "Подождать"]
TURN_LABELS = {"idle": "думает", "thinking": "думает", "action_chosen": "действие выбрано",
               "turn_ended": "ход закончен", "downed": "при смерти", "unconscious": "без сознания"}


def reader_hero(session: dict[str, Any], players: list[dict[str, Any]]) -> str | None:
    mode = world.settings_of(session).get("reader_mode", "off")
    with_heroes = [p for p in players if p["hero_id"]]
    if mode == "rotate" and with_heroes:
        return with_heroes[(session["scene_no"] - 1) % len(with_heroes)]["hero_id"]
    if mode == "volunteers":
        return next((p["hero_id"] for p in with_heroes if p["is_reader"]), None)
    return None


async def feed_for(db: AsyncSession, sid: str, audiences: tuple[str, ...], limit: int = 40) -> list[dict[str, Any]]:
    placeholders = ",".join(f":a{i}" for i in range(len(audiences)))
    params = {f"a{i}": a for i, a in enumerate(audiences)}
    found = await world.rows(
        db, f"SELECT id, audience, type, payload_json FROM ws_event WHERE session_id = :s "
            f"AND type IN ('narration.public','feed.message') AND audience IN ({placeholders}) "
            f"ORDER BY id DESC LIMIT :n", s=sid, n=limit, **params)
    items = []
    for r in reversed(found):
        payload = json.loads(r["payload_json"])
        payload["seq"] = r["id"]
        items.append(payload)
    return items


def lobby_block(session: dict[str, Any], players: list[dict[str, Any]]) -> dict[str, Any]:
    heroes = content.heroes_catalog()
    return {
        "players": [{"player_name": p["player_name"], "hero_id": p["hero_id"],
                     "hero_name": heroes[p["hero_id"]]["name"] if p["hero_id"] else None,
                     "ready": bool(p["ready"]), "sworn_oath": bool(p["sworn_oath"]),
                     "connected": False} for p in players],
        "taken_heroes": {p["hero_id"]: p["player_name"] for p in players if p["hero_id"]},
        "player_count": session["player_count"],
    }


async def open_votes(db: AsyncSession, sid: str) -> list[dict[str, Any]]:
    out = []
    for v in await world.rows(db, "SELECT * FROM setting_vote WHERE session_id = :s AND status = 'open' ORDER BY id", s=sid):
        out.append({"id": v["id"], "key": v["key"], "value": v["value"], "proposer": v["proposer"],
                    "votes": json.loads(v["votes_json"]), "rule": rules.SETTING_VOTE_RULE.get(
                        {"reader_mode": "reader"}.get(v["key"], v["key"]), "majority")})
    return out


async def _hero_positions(db: AsyncSession, sid: str) -> dict[str, dict[str, Any]]:
    return {h["hero_id"]: h for h in await world.all_hero_rows(db, sid)}


async def build_table_map_payload(db: AsyncSession, session: dict[str, Any]) -> dict[str, Any]:
    scenario = world.scenario_of(session)
    sid = session["id"]
    heroes = await _hero_positions(db, sid)
    return map_state.build_table_map(
        scenario, await world.visited_zones_global(db, sid), await world.clock_rows(db, sid),
        await world.active_locations(db, sid), await _task_levels_public(db, sid, scenario),
        {h: r["zone_id"] for h, r in heroes.items()})


async def _task_levels_public(db: AsyncSession, sid: str, scenario: dict[str, Any]) -> dict[str, int]:
    return await world.task_public_levels(db, sid)


async def build_table_state(db: AsyncSession, session: dict[str, Any], connected_heroes: set[str] | None = None) -> dict[str, Any]:
    sid = session["id"]
    repo = SessionRepository(db)
    players = await repo.players(sid)
    heroes_cat = content.heroes_catalog()
    story = content.story_by_id(session["story_id"]) or {}
    state: dict[str, Any] = {
        "session": {"code": session["join_code"], "name": session["name"], "status": session["status"],
                    "round_no": session["round_no"], "phase": session["round_phase"],
                    "story_id": session["story_id"], "story_title": story.get("title", session["story_id"]),
                    "player_count": session["player_count"], "settings": world.settings_of(session)},
        "lobby": lobby_block(session, players),
        "votes": await open_votes(db, sid),
        "reader": reader_hero(session, players),
        "feed": await feed_for(db, sid, ("table", "all")),
    }
    for p in state["lobby"]["players"]:
        p["connected"] = bool(connected_heroes and p["hero_id"] in connected_heroes)
    if session["status"] in ("playing", "paused", "finished"):
        scenario = world.scenario_of(session)
        hero_rows = {h["hero_id"]: h for h in await world.all_hero_rows(db, sid)}
        visited = await world.visited_zones_global(db, sid)
        state["map"] = await build_table_map_payload(db, session)
        state["players"] = []
        tiles: dict[str, list[str]] = {}
        for p in players:
            if not p["hero_id"]:
                continue
            h = hero_rows.get(p["hero_id"])
            zone = h["zone_id"] if h else None
            wounds = await world.wounds(db, sid, p["hero_id"])
            used = rules.cells_used(world.wound_objects(wounds))
            status = p["status"] if p["status"] in ("away", "ai") else p["turn_status"]
            state["players"].append({
                "hero_id": p["hero_id"], "hero_name": heroes_cat[p["hero_id"]]["name"],
                "title": heroes_cat[p["hero_id"]]["title"], "player_name": p["player_name"],
                "turn_status": p["turn_status"], "turn_label": TURN_LABELS.get(status, status),
                "away": p["status"] != "active", "zone_id": zone if zone in visited else None,
                "location_id": h["location_id"] if h else None,
                "endurance": h["endurance"] if h else None, "cells_used": used})
            if h:
                tiles.setdefault(h["location_id"], []).append(p["hero_id"])
        state["tiles"] = [{"location_id": loc, "name": scenario["locations"][loc]["name"], "hero_ids": ids}
                          for loc, ids in tiles.items()]
        state["split"] = len(tiles) > 1
        state["location_limit_reached"] = len(tiles) >= rules.MAX_OCCUPIED_LOCATIONS
    return state


def _hero_card(hero: dict[str, Any], hs: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "id": hero["id"], "name": hero["name"], "title": hero["title"], "stats": (hs or hero)["stats"],
        "endurance": hero["endurance"], "gift": hero["gift"], "weakness": hero["weakness"],
        "action_ability": hero["action_ability"], "minor_ability": hero["minor_ability"],
        "goal": {**hero["goal"], "progress": hs["goal_progress"] if hs else 0},
        "interrogation": hero["interrogation"],
    }


async def build_hand_state(db: AsyncSession, session: dict[str, Any], player: dict[str, Any]) -> dict[str, Any]:
    sid = session["id"]
    repo = SessionRepository(db)
    players = await repo.players(sid)
    heroes_cat = content.heroes_catalog()
    state: dict[str, Any] = {
        "session": {"code": session["join_code"], "name": session["name"], "status": session["status"],
                    "round_no": session["round_no"], "phase": session["round_phase"],
                    "story_title": (content.story_by_id(session["story_id"]) or {}).get("title"),
                    "settings": world.settings_of(session)},
        "me": {"player_name": player["player_name"], "hero_id": player["hero_id"], "ready": bool(player["ready"]),
               "sworn_oath": bool(player["sworn_oath"]), "turn_status": player["turn_status"]},
        "lobby": lobby_block(session, players),
        "votes": await open_votes(db, sid),
        "reader": {"hero_id": reader_hero(session, players)},
    }
    state["reader"]["is_me"] = bool(player["hero_id"]) and state["reader"]["hero_id"] == player["hero_id"]
    if not player["hero_id"] or session["status"] not in ("playing", "paused", "finished"):
        if player["hero_id"]:
            state["hero"] = _hero_card(heroes_cat[player["hero_id"]], None)
        return state

    hero_id = player["hero_id"]
    scenario = world.scenario_of(session)
    hero = heroes_cat[hero_id]
    hs = await world.hero_row(db, sid, hero_id)
    wound_rows = await world.wounds(db, sid, hero_id)
    wound_objs = world.wound_objects(wound_rows)
    visited = await world.visited_zones_hero(db, sid, hero_id)
    zone_id = hs["zone_id"]
    all_heroes = await world.all_hero_rows(db, sid)
    here = [h["hero_id"] for h in all_heroes if h["zone_id"] == zone_id and h["hero_id"] != hero_id]

    card = _hero_card(hero, hs)
    card.update({
        "fate": hs["fate"], "minor_ready": hs["abilities"].get("minor_ready", True),
        "inventory": [i for i in hs["inventory"]], "slots": 4,
        "wounds": [{"body_part": w["body_part"], "side": w["side"], "severity": w["severity"], "cells": w["cells"]}
                   for w in wound_rows],
        "cells_used": rules.cells_used(wound_objs), "penalty": rules.total_wound_penalty(wound_objs),
        "downed": rules.is_downed(rules.cells_used(wound_objs), hero["endurance"]),
        "secrets": {"story": {"state": hs["secrets"]["story"],
                              "text": hero["secrets"]["story"] if hs["secrets"]["story"] == "known" else None},
                    "personal": {"state": hs["secrets"]["personal"],
                                 "text": hero["secrets"]["personal"] if hs["secrets"]["personal"] == "known" else None}},
    })
    state["hero"] = card

    facts = await world.facts_of_hero(db, sid, hero_id)
    levels = await world.hero_task_levels(db, sid, hero_id)
    known_tasks = []
    for t in scenario["tasks"]:
        lvl = levels.get(t["id"], 0)
        if lvl >= 1:
            known_tasks.append({"id": t["id"], "level": lvl, "text": t["levels"][lvl],
                                "title": t["title"] if lvl >= 2 else None, "zone": t["zone"] if lvl >= 2 else None})
    state["tasks"] = known_tasks
    state["facts"] = [f for f in facts if not f["id"].startswith("task:")]
    state["clues"] = [f for f in facts if f["id"].startswith("clue:")]

    chip_tasks = [{"id": t["id"], "level": levels.get(t["id"], 0), "known_by": [hero_id],
                   "phrases": {int(k): v for k, v in t.get("chip_phrases", {}).items()}, "updated_round": 0}
                  for t in scenario["tasks"]]
    state["chips"] = rules.build_chips(chip_tasks, hero_id, SIMPLE_CHIPS, rotation=session["round_no"])

    zone_level = max([levels.get(t["id"], 0) for t in scenario["tasks"] if t["zone"] == zone_id] or [0])
    view_levels = {int(k): v for k, v in scenario.get("views", {}).get(zone_id, {}).items()}
    best = max([k for k in view_levels if k <= zone_level] or [0])
    image = view_levels.get(best)
    state["view"] = {"zone_id": zone_id, "zone_name": scenario["zone_names"][zone_id], "level": zone_level,
                     "image": image, "image_url": (f"/assets/{image}.webp"
                                                   if image and (content.ASSETS_DIR / f"{image}.webp").exists() else None)}

    task_zones = {t["zone"] for t in scenario["tasks"] if levels.get(t["id"], 0) >= 1}
    state["map"] = map_state.build_personal_map(scenario, hero_id, visited, zone_id, here, task_zones)
    state["heard_by"] = [{"hero_id": h, "name": heroes_cat[h]["name"]} for h in here]
    state["feed"] = await feed_for(db, sid, ("all", f"hero:{hero_id}"))
    state["terrain"] = [t for t in scenario.get("terrain", []) if t["zone"] == zone_id]
    pending = await world.row(
        db, "SELECT id, parsed_json, status FROM action WHERE session_id = :s AND hero_id = :h AND round_no = :r "
            "AND status IN ('draft','confirmed') ORDER BY id DESC", s=sid, h=hero_id, r=session["round_no"])
    state["pending_action"] = ({"id": pending["id"], "status": pending["status"],
                                "card": json.loads(pending["parsed_json"] or "{}").get("card")} if pending else None)
    state["consent_requests"] = await consent_requests_for(db, session, hero_id)
    state["moved_pending"] = hs.get("pending_zone")
    return state


async def consent_requests_for(db: AsyncSession, session: dict[str, Any], hero_id: str) -> list[dict[str, Any]]:
    out = []
    heroes_cat = content.heroes_catalog()
    for a in await world.rows(db, "SELECT id, hero_id, parsed_json FROM action WHERE session_id = :s AND round_no = :r "
                                  "AND status = 'confirmed'", s=session["id"], r=session["round_no"]):
        parsed = json.loads(a["parsed_json"] or "{}")
        consents = parsed.get("consents", {})
        if consents.get(hero_id) == "pending":
            out.append({"action_id": a["id"], "from_hero": a["hero_id"],
                        "from_name": heroes_cat[a["hero_id"]]["name"], "intent": parsed.get("intent", "")})
    return out
