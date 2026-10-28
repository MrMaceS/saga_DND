"""Жизненный цикл вечера: старт, «Закончить ход», разрешение раунда, часы, кат-сцены, автосохранение."""
import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.narrator import narrate
from app.ai.fallback import narrator_fallback
from app.ai.service import get_ai_client
from app.config import settings
from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.engine import content
from app.engine.dice_provider import get_roller
from app.engine.scenario_loader import add_fact, initialize_scenario
from app.services import actions, world
from app.services.savegame import autosave
from app.services.sync import publish, push_states
from engine import rules

logger = logging.getLogger(__name__)


async def _fresh(db: AsyncSession, sid: str) -> dict[str, Any]:
    return await world.row(db, "SELECT * FROM game_session WHERE id = :s", s=sid)


# ----------------------------------------------------------------- старт
async def start_session(db: AsyncSession, session: dict[str, Any]) -> None:
    if session["status"] != "lobby":
        raise SagaError("invalid_state", "Сага уже началась")
    repo = SessionRepository(db)
    players = await repo.players(session["id"])
    if len(players) < 2:
        raise SagaError("not_ready", "Нужно минимум 2 игрока")
    waiting = [p["player_name"] for p in players if not (p["hero_id"] and p["ready"] and p["sworn_oath"])]
    if waiting:
        raise SagaError("not_ready", "Не готовы: " + ", ".join(waiting))

    sid = session["id"]
    scenario = await initialize_scenario(db, sid, session["story_id"],
                                         [{"hero_id": p["hero_id"], "player_name": p["player_name"]} for p in players])
    await db.execute(text("UPDATE game_session SET status = 'playing', round_no = 1, round_phase = 'declaring', "
                          "scene_no = 1, player_count = :n WHERE id = :s"), {"n": len(players), "s": sid})
    await db.execute(text("UPDATE player_binding SET turn_status = 'idle' WHERE session_id = :s"), {"s": sid})
    await db.commit()
    for cs in scenario.get("cutscenes", []):
        if cs["trigger"] == "scene_start":
            await play_cutscene(db, sid, cs["id"], 1)
    await autosave(db, sid)
    await push_states(db, sid)


async def play_cutscene(db: AsyncSession, sid: str, cutscene_id: str, round_no: int, extra_text: str | None = None) -> None:
    payload = content.cutscene_payload(cutscene_id)
    if not payload:
        logger.warning("Нет данных кат-сцены %s", cutscene_id)
        return
    await publish(db, sid, "table", "cutscene.play", payload)
    narration = " ".join(s["text"] for s in payload["subtitles"])
    await publish(db, sid, "all", "narration.public", {"kind": "cutscene", "cutscene_id": cutscene_id,
                                                       "round": round_no, "text": narration})
    await db.execute(text("INSERT INTO story_event (session_id, round_no, type, payload_json, public_text) "
                          "VALUES (:s, :r, 'cutscene', :p, :t)"),
                     {"s": sid, "r": round_no, "p": json.dumps({"id": cutscene_id}), "t": narration})
    await db.commit()


# ------------------------------------------------------------ конец хода
async def end_turn(db: AsyncSession, session: dict[str, Any], player: dict[str, Any]) -> None:
    if session["status"] != "playing" or session["round_phase"] != "declaring":
        raise SagaError("invalid_phase")
    if not player["hero_id"]:
        raise SagaError("forbidden")
    await db.execute(text("UPDATE player_binding SET turn_status = 'turn_ended' WHERE session_id = :s AND hero_id = :h "
                          "AND turn_status NOT IN ('downed','unconscious')"),
                     {"s": session["id"], "h": player["hero_id"]})
    await db.commit()
    await maybe_resolve(db, session["id"])


async def unend_turn(db: AsyncSession, session: dict[str, Any], player: dict[str, Any]) -> None:
    if session["round_phase"] != "declaring":
        raise SagaError("invalid_phase", "Раунд уже разрешается")
    has_action = await world.row(
        db, "SELECT id FROM action WHERE session_id = :s AND hero_id = :h AND round_no = :r AND status = 'confirmed'",
        s=session["id"], h=player["hero_id"], r=session["round_no"])
    await db.execute(text("UPDATE player_binding SET turn_status = :t WHERE session_id = :s AND hero_id = :h "
                          "AND turn_status = 'turn_ended'"),
                     {"t": "action_chosen" if has_action else "idle", "s": session["id"], "h": player["hero_id"]})
    await db.commit()


async def maybe_resolve(db: AsyncSession, sid: str) -> bool:
    session = await _fresh(db, sid)
    if session["status"] != "playing" or session["round_phase"] != "declaring":
        return False
    players = [p for p in await SessionRepository(db).players(sid) if p["hero_id"]]
    statuses = {p["hero_id"]: (p["status"] if p["status"] in ("away", "ai") else p["turn_status"]) for p in players}
    if not rules.all_ready(statuses) or not any(p["turn_status"] == "turn_ended" for p in players):
        return False
    await resolve_round(db, sid)
    return True


# ------------------------------------------------------------------ раны
async def apply_wound(db: AsyncSession, session: dict[str, Any], hero_id: str, severity: rules.Severity,
                      part: rules.BodyPart) -> None:
    sid = session["id"]
    hero = content.heroes_catalog()[hero_id]
    w = rules.Wound(severity, part)
    await db.execute(text("INSERT INTO injury (session_id, hero_id, body_part, side, severity, cells, round_no) "
                          "VALUES (:s, :h, :p, :side, :sev, :c, :r)"),
                     {"s": sid, "h": hero_id, "p": part.value, "side": "right" if part == rules.BodyPart.ARM else None,
                      "sev": severity.value, "c": w.cells, "r": session["round_no"]})
    used = rules.cells_used(world.wound_objects(await world.wounds(db, sid, hero_id)))
    if rules.is_downed(used, hero["endurance"]):
        await db.execute(text("UPDATE player_binding SET turn_status = 'downed' WHERE session_id = :s AND hero_id = :h"),
                         {"s": sid, "h": hero_id})
        await db.execute(text("UPDATE hero_state SET dying_clock = :c WHERE session_id = :s AND hero_id = :h"),
                         {"c": rules.DYING_CLOCK_START, "s": sid, "h": hero_id})
    await db.commit()


# ------------------------------------------------------- разрешение раунда
async def _apply_clock_delta(db: AsyncSession, sid: str, clock_id: str, delta: int) -> int:
    row = await world.row(db, "SELECT filled, segments FROM clock WHERE session_id = :s AND id = :c", s=sid, c=clock_id)
    new = max(0, min(row["segments"], row["filled"] + delta))
    await db.execute(text("UPDATE clock SET filled = :f WHERE session_id = :s AND id = :c"), {"f": new, "s": sid, "c": clock_id})
    return new - row["filled"]


async def _resolve_investigate(db: AsyncSession, session: dict[str, Any], scenario: dict[str, Any],
                               action: dict[str, Any], parsed: dict[str, Any], participants: list[str]) -> dict[str, Any]:
    sid, hero_id = session["id"], action["hero_id"]
    heroes = content.heroes_catalog()
    name = heroes[hero_id]["name"].split()[0]
    hs = await world.hero_row(db, sid, hero_id)
    zone = hs["zone_id"]
    task = (next((t for t in scenario["tasks"] if t["id"] == parsed.get("target_task")), None)
            or next((t for t in scenario["tasks"] if t["zone"] == zone), None))
    if task is None or task["zone"] != zone:
        return {"hero_id": hero_id, "no_roll": True,
                "text": f"{name} осматривается, но не находит ничего примечательного."}

    levels = await world.hero_task_levels(db, sid, hero_id)
    current = levels.get(task["id"], 0)
    stat_key = parsed.get("required_stat", "wits")
    wound_mod = rules.total_wound_penalty(world.wound_objects(await world.wounds(db, sid, hero_id)))
    group = bool(task.get("group_bonus"))
    tags = [t for t in parsed.get("difficulty_tags", []) if t in rules.TAG_MODS] + actions.world_tags(
        scenario, hs["inventory"], alone=group and len(participants) == 1, with_partner=group and len(participants) > 1)
    base = scenario["rolls"].get(task["id"], {}).get("base", parsed.get("base", "normal"))
    dc = rules.compute_difficulty(base, tags)
    roll = get_roller().roll_d20(hs["stats"][stat_key] + wound_mod, dc)
    await db.execute(
        text("INSERT INTO dice_roll (session_id, round_no, hero_id, kind, stat, natural, modifier, difficulty, outcome) "
             "VALUES (:s, :r, :h, 'check', :st, :n, :m, :dc, :o)"),
        {"s": sid, "r": session["round_no"], "h": hero_id, "st": stat_key, "n": roll.natural,
         "m": hs["stats"][stat_key] + wound_mod, "dc": dc, "o": roll.outcome.value})
    await db.commit()
    await publish(db, sid, "all", "roll.public", {
        "hero_id": hero_id, "hero_name": heroes[hero_id]["name"], "kind": "check",
        "label": f"{actions.STAT_LABELS[stat_key]} · {task['title'] if current >= 2 else 'проверка'}",
        "natural": roll.natural, "modifier": hs["stats"][stat_key] + wound_mod, "dc": dc, "outcome": roll.outcome.value})

    table = scenario["rolls"].get(task["id"], {}).get("outcomes", {}).get(roll.outcome.value, {})
    gain = table.get("info_level", rules.info_gain(roll.outcome, False))
    new_level = rules.raise_level(current, gain)
    revealed: list[str] = []
    for lvl in range(current + 1, new_level + 1):
        revealed.append(task["levels"][lvl])
        await add_fact(db, sid, f"task:{task['id']}:{lvl}", task["levels"][lvl], lvl, "own_action",
                       session["round_no"], participants)
    for h in participants:  # общие знания участников совместного действия
        for lvl in range(1, new_level + 1):
            await db.execute(text("INSERT OR IGNORE INTO fact_known_by (session_id, fact_id, hero_id) VALUES (:s, :f, :h)"),
                             {"s": sid, "f": f"task:{task['id']}:{lvl}", "h": h})
    if new_level > current:
        await db.execute(text("UPDATE task SET public_level = MAX(public_level, :l) WHERE session_id = :s AND id = :t"),
                         {"l": new_level, "s": sid, "t": task["id"]})
        closes = task.get("closes_clock_at_level")
        if closes and new_level >= closes and task.get("ignored_clock"):
            await db.execute(text("UPDATE clock SET resolved = 1 WHERE session_id = :s AND id = :c"),
                             {"s": sid, "c": task["ignored_clock"]})

    effects: list[str] = list(table.get("effects", []))
    for item_id in table.get("items", []):
        defn = scenario.get("item_defs", {}).get(item_id, {"name": item_id, "kind": "item"})
        if defn["kind"] == "clue":
            await add_fact(db, sid, f"clue:{item_id}", defn["text"], 1, "own_action", session["round_no"], participants)
            revealed.append(defn["text"])
        else:
            inv = (await world.hero_row(db, sid, hero_id))["inventory"]
            if len(inv) < 4:
                inv.append(defn["name"])
                await db.execute(text("UPDATE hero_state SET inventory_json = :i WHERE session_id = :s AND hero_id = :h"),
                                 {"i": json.dumps(inv, ensure_ascii=False), "s": sid, "h": hero_id})
                revealed.append(f"Ты находишь: {defn['name']}.")
            else:
                revealed.append(f"Ты находишь {defn['name']}, но рюкзак полон.")

    clocks_changed: dict[str, int] = {}
    for clock_id, delta in table.get("clocks", {}).items():
        applied = await _apply_clock_delta(db, sid, clock_id, delta)
        if applied:
            clocks_changed[clock_id] = applied
    await db.commit()

    for effect in effects:
        if effect == "torch_out":
            inv = (await world.hero_row(db, sid, hero_id))["inventory"]
            inv = [i for i in inv if "факел" not in i.lower()]
            await db.execute(text("UPDATE hero_state SET inventory_json = :i WHERE session_id = :s AND hero_id = :h"),
                             {"i": json.dumps(inv, ensure_ascii=False), "s": sid, "h": hero_id})
        elif effect == "grab_check_10":
            grab = get_roller().roll_d20(max(hs["stats"]["strength"], hs["stats"]["agility"]) + wound_mod, 10)
            if grab.outcome in (rules.Outcome.CRITICAL_FAIL, rules.Outcome.FAIL, rules.Outcome.FAIL_WITH_CONSEQUENCE):
                await apply_wound(db, session, hero_id, rules.Severity.LIGHT, rules.BodyPart.ARM)
                effects.append("injury: right arm, light")
        elif effect == "light_wound_first_hero_in_zone":
            await apply_wound(db, session, hero_id, rules.Severity.LIGHT, rules.BodyPart.ARM)
            effects.append("injury: right arm, light")
    await db.commit()
    return {"hero_id": hero_id, "participants": participants, "task_id": task["id"], "outcome": roll.outcome.value,
            "revealed": revealed, "effects": effects, "clocks_changed": clocks_changed, "intent": parsed.get("intent", "")}


async def _was_triggered(db: AsyncSession, sid: str, key: str) -> bool:
    return bool(await world.row(db, "SELECT id FROM story_event WHERE session_id = :s AND type = 'trigger' "
                                    "AND payload_json = :p", s=sid, p=json.dumps({"key": key})))


async def _mark_triggered(db: AsyncSession, sid: str, key: str, round_no: int) -> None:
    await db.execute(text("INSERT INTO story_event (session_id, round_no, type, payload_json) VALUES (:s, :r, 'trigger', :p)"),
                     {"s": sid, "r": round_no, "p": json.dumps({"key": key})})


async def resolve_round(db: AsyncSession, sid: str) -> None:
    session = await _fresh(db, sid)
    if session["round_phase"] != "declaring":
        return
    scenario = world.scenario_of(session)
    heroes = content.heroes_catalog()
    round_no = session["round_no"]
    await db.execute(text("UPDATE game_session SET round_phase = 'resolving' WHERE id = :s"), {"s": sid})
    await db.commit()
    await publish(db, sid, "all", "round.resolving", {"round": round_no})
    await push_states(db, sid)

    clocks_before = {c["id"]: c["filled"] for c in await world.clock_rows(db, sid)}

    # 1. заявки (совместные считаются один раз)
    results: list[dict[str, Any]] = []
    handled: set[str] = set()
    for a in await world.rows(db, "SELECT * FROM action WHERE session_id = :s AND round_no = :r AND status = 'confirmed' "
                                  "ORDER BY id", s=sid, r=round_no):
        if a["hero_id"] in handled:
            continue
        parsed = json.loads(a["parsed_json"])
        partners = [h for h, v in parsed.get("consents", {}).items() if v == "accept"]
        participants = [a["hero_id"], *partners]
        handled.update(participants)
        if parsed["action_type"] == "investigate":
            results.append(await _resolve_investigate(db, session, scenario, a, parsed, participants))
        await db.execute(text("UPDATE action SET status = 'resolved' WHERE id = :i"), {"i": a["id"]})
    await db.commit()

    # 2. переходы между локациями завершаются в конце раунда
    for h in await world.all_hero_rows(db, sid):
        if h["pending_zone"]:
            await actions.arrive(db, session, h["hero_id"], h["pending_zone"])

    # 3. часы активных локаций тикают
    active = await world.active_locations(db, sid)
    clocks = [{"id": c["id"], "location": c["location_id"], "filled": c["filled"], "segments": c["segments"],
               "resolved": bool(c["resolved"])} for c in await world.clock_rows(db, sid)]
    ticked, _ = rules.tick_clocks(clocks, active)
    for c in ticked:
        await db.execute(text("UPDATE clock SET filled = :f WHERE session_id = :s AND id = :c"),
                         {"f": c["filled"], "s": sid, "c": c["id"]})
    await db.commit()

    # 4. нарратив результатов
    client = get_ai_client()
    for res in results:
        if res.get("no_roll"):
            await publish(db, sid, "all", "narration.public", {"kind": "public", "round": round_no, "text": res["text"]})
            continue
        clock_meta = {c["id"]: c for c in scenario["clocks"]}
        engine_result = {
            "hero_profile": {"id": res["hero_id"], "name": heroes[res["hero_id"]]["name"],
                             "title": heroes[res["hero_id"]]["title"]},
            "action": res["intent"], "intent": res["intent"], "outcome": res["outcome"], "effects": res["effects"],
            "revealed": res["revealed"], "clocks_changed": res["clocks_changed"],
            "clock_phrases": [clock_meta[c]["change_phrase"] for c in res["clocks_changed"]
                              if clock_meta.get(c, {}).get("change_phrase")],
            "scene_facts": scenario.get("scene_facts", []), "enemy_facts": {},
            "cruelty": world.settings_of(session).get("cruelty", "restrained"),
        }
        narration = (await narrate(client, settings.model_narrator, engine_result)) if client else narrator_fallback(engine_result)
        if narration.get("public"):
            await publish(db, sid, "all", "narration.public", {"kind": "public", "round": round_no,
                                                               "text": narration["public"], "hero_id": res["hero_id"]})
        for hid in res.get("participants", [res["hero_id"]]):
            private = narration.get("private", {}).get(hid) or (" ".join(res["revealed"]) if hid == res["hero_id"] else "")
            if private:
                await publish(db, sid, f"hero:{hid}", "feed.message", {"kind": "private", "round": round_no, "text": private})

    # 5. сработавшие часы и кат-сцены
    clocks_after = {c["id"]: c["filled"] for c in await world.clock_rows(db, sid)}
    for sc in scenario["clocks"]:
        before, after = clocks_before[sc["id"]], clocks_after[sc["id"]]
        for milestone, cs_id in (sc.get("cutscene_at") or {}).items():
            key = f"clock:{sc['id']}:{milestone}"
            if before < milestone <= after and not await _was_triggered(db, sid, key):
                await _mark_triggered(db, sid, key, round_no)
                await play_cutscene(db, sid, cs_id, round_no)
        if before < sc["segments"] == after:
            key = f"clock:{sc['id']}:full"
            if not await _was_triggered(db, sid, key):
                await _mark_triggered(db, sid, key, round_no)
                if sc.get("cutscene_on_full"):
                    await play_cutscene(db, sid, sc["cutscene_on_full"], round_no)
                elif sc.get("on_full_text"):
                    await publish(db, sid, "all", "narration.public", {"kind": "public", "round": round_no,
                                                                       "text": sc["on_full_text"]})
    levels = await world.task_public_levels(db, sid)
    for cs in scenario.get("cutscenes", []):
        if cs["trigger"] == "task_level" and levels.get(cs["task"], 0) >= cs["level"]:
            key = f"task:{cs['task']}:{cs['level']}"
            if not await _was_triggered(db, sid, key):
                await _mark_triggered(db, sid, key, round_no)
                await play_cutscene(db, sid, cs["id"], round_no)
    await db.commit()

    # 6. следующий раунд
    await db.execute(text("UPDATE game_session SET round_no = round_no + 1, round_phase = 'declaring' WHERE id = :s"), {"s": sid})
    await db.execute(text("UPDATE player_binding SET turn_status = 'idle' WHERE session_id = :s "
                          "AND turn_status NOT IN ('downed','unconscious')"), {"s": sid})
    await db.commit()
    await autosave(db, sid)
    await publish(db, sid, "all", "round.started", {"round": round_no + 1})
    await push_states(db, sid)
