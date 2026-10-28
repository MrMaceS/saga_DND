"""Действия игрока: разбор текста, подтверждение, согласия, окрик и шёпот, шаги по зонам."""
import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.interpreter import interpret_action
from app.ai.service import get_ai_client
from app.config import settings
from app.domain.errors import SagaError
from app.engine import content, map_state
from app.engine.dice_provider import get_roller
from app.engine.scenario_loader import add_fact
from app.services import world
from app.services.sync import publish
from engine import rules

STAT_LABELS = {"strength": "Сила", "agility": "Ловкость", "wits": "Разум", "spirit": "Дух"}
ACTION_LABELS = {"investigate": "Исследовать", "sneak": "Осторожно перейти", "move": "Перейти", "wait": "Ждать",
                 "talk": "Сказать", "propose": "Попросить", "combat": "Бой"}
IMPLEMENTED = {"investigate", "sneak", "move", "wait", "talk", "propose"}


def world_tags(scenario: dict[str, Any], inventory: list[str], alone: bool, with_partner: bool) -> list[str]:
    """Условия мира добавляет сервер (число игроков в сложность не входит)."""
    tags: list[str] = []
    if scenario.get("time") == "night":
        tags.append("dark")
    if scenario.get("light") == "dark" and not any("факел" in i.lower() for i in inventory):
        tags.append("no_light")
    if alone:
        tags.append("alone")
    if with_partner:
        tags.append("with_partner")
    return tags


def _cross_link(scenario: dict[str, Any], a: str, b: str) -> bool:
    return any({l["from"], l["to"]} == {a, b} for l in scenario.get("cross_location_links", []))


async def build_context(db: AsyncSession, session: dict[str, Any], hero_id: str) -> dict[str, Any]:
    """Контекст интерпретатора: только то, что известно этому герою."""
    sid = session["id"]
    scenario = world.scenario_of(session)
    hs = await world.hero_row(db, sid, hero_id)
    visited = await world.visited_zones_hero(db, sid, hero_id)
    levels = await world.hero_task_levels(db, sid, hero_id)
    task_zones = {t["zone"] for t in scenario["tasks"] if levels.get(t["id"], 0) >= 1}
    visible = map_state.visible_zone_ids(visited | {hs["zone_id"]}, scenario["adjacency"], task_zones)
    heroes = content.heroes_catalog()
    others = []
    for h in await world.all_hero_rows(db, sid):
        if h["hero_id"] == hero_id:
            continue
        others.append({"id": h["hero_id"], "names": [heroes[h["hero_id"]]["name"].split()[0]],
                       "zone": h["zone_id"] if h["zone_id"] in visible else None})
    return {
        "hero_id": hero_id, "current_zone": hs["zone_id"], "zones": sorted(visible),
        "zone_names": {z: scenario["zone_names"][z] for z in visited},
        "zone_aliases": {z: scenario.get("zone_aliases", {}).get(z, []) for z in visible},
        "tasks": [{"id": t["id"], "level": levels[t["id"]], "zone": t["zone"],
                   "phrases": {int(k): v for k, v in t.get("chip_phrases", {}).items()}}
                  for t in scenario["tasks"] if levels.get(t["id"], 0) >= 1],
        "enemies": [], "terrain": [t for t in scenario.get("terrain", []) if t["zone"] == hs["zone_id"]],
        "items": hs["inventory"], "abilities": [], "others_in_scene": others,
    }


async def _pending_state(db: AsyncSession, session: dict[str, Any], hero_id: str) -> str:
    row = await world.row(db, "SELECT turn_status FROM player_binding WHERE session_id = :s AND hero_id = :h",
                          s=session["id"], h=hero_id)
    return row["turn_status"] if row else "idle"


def _require_declaring(session: dict[str, Any]) -> None:
    if session["status"] != "playing" or session["round_phase"] != "declaring":
        raise SagaError("invalid_phase")


async def submit_text(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], raw_text: str) -> dict[str, Any]:
    _require_declaring(session)
    hero_id = player["hero_id"]
    raw_text = " ".join(raw_text.split())[:300]
    if not raw_text:
        raise SagaError("action_unavailable", "Опишите, что делает герой")
    if player["turn_status"] == "turn_ended":
        raise SagaError("invalid_phase", "Сначала снимите «Закончить ход»")
    if player["turn_status"] in ("downed", "unconscious"):
        raise SagaError("action_unavailable", "Герой не может действовать")

    sid = session["id"]
    scenario = world.scenario_of(session)
    context = await build_context(db, session, hero_id)
    client = get_ai_client()
    if client is not None:
        parsed = await interpret_action(client, settings.model_interpreter, hero_id, raw_text, context)
    else:
        from app.ai.local_interpreter import interpret_local
        parsed = interpret_local(raw_text, context)
    parsed["hero_id"] = hero_id

    hs = await world.hero_row(db, sid, hero_id)
    card = await _make_card(db, session, scenario, hs, parsed)
    parsed["card"] = card

    # Новая заявка заменяет прежние неподтверждённые черновики.
    await db.execute(text("UPDATE action SET status = 'rejected' WHERE session_id = :s AND hero_id = :h "
                          "AND round_no = :r AND status = 'draft'"), {"s": sid, "h": hero_id, "r": session["round_no"]})
    res = await db.execute(
        text("INSERT INTO action (session_id, round_no, hero_id, raw_text, parsed_json, status) "
             "VALUES (:s, :r, :h, :raw, :p, 'draft')"),
        {"s": sid, "r": session["round_no"], "h": hero_id, "raw": raw_text,
         "p": json.dumps(parsed, ensure_ascii=False)})
    action_id = res.lastrowid
    await db.execute(text("UPDATE player_binding SET turn_status = 'thinking' WHERE session_id = :s AND hero_id = :h "
                          "AND turn_status IN ('idle','thinking')"), {"s": sid, "h": hero_id})
    await db.commit()
    payload = {"action_id": action_id, "raw_text": raw_text, "card": card}
    await publish(db, sid, f"hero:{hero_id}", "action.recognized", payload)
    return payload


async def _make_card(db: AsyncSession, session: dict[str, Any], scenario: dict[str, Any],
                     hs: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    heroes = content.heroes_catalog()
    atype = parsed["action_type"]
    card: dict[str, Any] = {
        "action_type": atype, "label": ACTION_LABELS.get(atype, atype), "intent": parsed.get("intent"),
        "stat": STAT_LABELS.get(parsed.get("required_stat", ""), ""), "difficulty": None, "no_roll": True,
        "needs_clarification": bool(parsed.get("needs_clarification")),
        "clarifying_question": parsed.get("clarifying_question"), "is_possible": bool(parsed.get("is_possible", True)),
        "rejection_reason": parsed.get("rejection_reason"), "alternative": parsed.get("alternative"),
        "free_actions": parsed.get("free_actions", []), "tags": parsed.get("difficulty_tags", []),
        "consent_from": [{"hero_id": h, "name": heroes[h]["name"]} for h in parsed.get("needs_consent_from", [])
                         if h in heroes],
        "side_action": None, "target": None, "move_to": None,
    }
    side = parsed.get("side_action")
    if side:
        card["side_action"] = {"type": side["type"], "target_hero": side["target_hero"],
                               "target_name": heroes.get(side["target_hero"], {}).get("name"),
                               "content": side.get("content")}

    def reject(reason: str, alt: str | None = "Осмотреться") -> dict[str, Any]:
        card.update(is_possible=False, rejection_reason=reason, alternative=alt)
        return card

    if card["needs_clarification"]:
        return card
    if not card["is_possible"]:
        return card
    if atype == "combat":
        return reject("Здесь пока не с кем драться.")
    if atype not in IMPLEMENTED:
        return reject("Это действие пока недоступно в игре.")

    adjacency = scenario["adjacency"]
    current = hs["zone_id"]
    zone = parsed.get("target_zone")
    if atype in ("investigate", "sneak", "move") and zone is None and parsed.get("target_task"):
        zone = next((t["zone"] for t in scenario["tasks"] if t["id"] == parsed["target_task"]), None)
    if zone:
        dist = rules.zone_distance(adjacency, current, zone)
        if dist is None or dist > 1:
            return reject("Туда не добраться за один ход.", "Подойти ближе")
        card["move_to"] = zone if dist == 1 else None
        card["cross_location"] = bool(dist == 1 and _cross_link(scenario, current, zone))
        visited = await world.visited_zones_hero(db, session["id"], hs["hero_id"])
        card["target"] = scenario["zone_names"][zone] if zone in visited else "незнакомое место"
    if parsed.get("target_task"):
        levels = await world.hero_task_levels(db, session["id"], hs["hero_id"])
        task = next((t for t in scenario["tasks"] if t["id"] == parsed["target_task"]), None)
        if task:
            card["target"] = task["levels"][levels[task["id"]]] if levels.get(task["id"], 0) >= 1 else card["target"]

    if atype == "investigate":
        task = _pick_task(scenario, parsed, zone or current)
        card["no_roll"] = task is None
        if task:
            alone = bool(task.get("group_bonus")) and not parsed.get("needs_consent_from")
            tags = list(parsed.get("difficulty_tags", [])) + world_tags(
                scenario, hs["inventory"], alone, bool(parsed.get("needs_consent_from")) and bool(task.get("group_bonus")))
            base = scenario["rolls"].get(task["id"], {}).get("base", parsed.get("base", "normal"))
            card["difficulty"] = rules.compute_difficulty(base, [t for t in tags if t in rules.TAG_MODS])
            card["stat"] = STAT_LABELS[parsed["required_stat"]]
    if atype == "propose" and not parsed.get("needs_consent_from"):
        return reject("Не понятно, кого просить.")
    return card


def _pick_task(scenario: dict[str, Any], parsed: dict[str, Any], zone: str) -> dict[str, Any] | None:
    tasks = scenario["tasks"]
    if parsed.get("target_task"):
        return next((t for t in tasks if t["id"] == parsed["target_task"]), None)
    return next((t for t in tasks if t["zone"] == zone), None)


async def confirm_action(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], action_id: int) -> None:
    _require_declaring(session)
    sid, hero_id = session["id"], player["hero_id"]
    row = await world.row(db, "SELECT * FROM action WHERE id = :i AND session_id = :s AND hero_id = :h",
                          i=action_id, s=sid, h=hero_id)
    if not row or row["status"] != "draft" or row["round_no"] != session["round_no"]:
        raise SagaError("not_found", "Заявка не найдена")
    parsed = json.loads(row["parsed_json"])
    card = parsed["card"]
    if card["needs_clarification"] or not card["is_possible"]:
        raise SagaError("action_unavailable", card.get("rejection_reason") or "Заявку нужно уточнить")

    # бесплатные действия выполняются сразу
    if parsed.get("side_action"):
        await communicate(db, session, hero_id, parsed["side_action"])
    if card["action_type"] == "talk":
        await speak(db, session, hero_id, parsed.get("free_actions", [None])[0] or parsed.get("intent", ""))
    for line in parsed.get("free_actions", []):
        if card["action_type"] != "talk" and line:
            await speak(db, session, hero_id, line)

    moved = False
    if card["action_type"] in ("move", "sneak") or (card["action_type"] == "investigate" and card.get("move_to")):
        if card.get("move_to"):
            await move_hero(db, session, hero_id, card["move_to"])
            moved = True
    if card["action_type"] in ("move", "sneak"):
        await db.execute(text("UPDATE action SET status = 'resolved' WHERE id = :i"), {"i": action_id})
        await db.execute(text("UPDATE player_binding SET turn_status = 'idle' WHERE session_id = :s AND hero_id = :h"),
                         {"s": sid, "h": hero_id})
        await db.commit()
        return

    parsed["consents"] = {h: "pending" for h in parsed.get("needs_consent_from", [])}
    parsed["moved"] = moved
    await db.execute(text("UPDATE action SET status = 'confirmed', parsed_json = :p WHERE id = :i"),
                     {"p": json.dumps(parsed, ensure_ascii=False), "i": action_id})
    await db.execute(text("UPDATE player_binding SET turn_status = :t WHERE session_id = :s AND hero_id = :h"),
                     {"t": "action_chosen", "s": sid, "h": hero_id})
    await db.commit()
    heroes = content.heroes_catalog()
    for target in parsed["consents"]:
        await publish(db, sid, f"hero:{target}", "feed.message", {
            "kind": "system", "round": session["round_no"],
            "text": f"{heroes[hero_id]['name'].split()[0]} зовёт тебя: {parsed.get('intent', '')}"})


async def cancel_action(db: AsyncSession, session: dict[str, Any], player: dict[str, Any]) -> None:
    _require_declaring(session)
    await db.execute(text("UPDATE action SET status = 'rejected' WHERE session_id = :s AND hero_id = :h AND round_no = :r "
                          "AND status IN ('draft','confirmed')"),
                     {"s": session["id"], "h": player["hero_id"], "r": session["round_no"]})
    await db.execute(text("UPDATE player_binding SET turn_status = 'idle' WHERE session_id = :s AND hero_id = :h "
                          "AND turn_status IN ('thinking','action_chosen','in_group_action')"),
                     {"s": session["id"], "h": player["hero_id"]})
    await db.commit()


async def consent_respond(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], action_id: int,
                          accept: bool) -> None:
    _require_declaring(session)
    sid, hero_id = session["id"], player["hero_id"]
    row = await world.row(db, "SELECT * FROM action WHERE id = :i AND session_id = :s AND status = 'confirmed'",
                          i=action_id, s=sid)
    if not row:
        raise SagaError("not_found", "Предложение не найдено")
    parsed = json.loads(row["parsed_json"])
    if parsed.get("consents", {}).get(hero_id) != "pending":
        raise SagaError("forbidden", "Это предложение не для вас")
    parsed["consents"][hero_id] = "accept" if accept else "decline"
    await db.execute(text("UPDATE action SET parsed_json = :p WHERE id = :i"),
                     {"p": json.dumps(parsed, ensure_ascii=False), "i": action_id})
    if accept:
        await db.execute(text("UPDATE action SET status = 'rejected' WHERE session_id = :s AND hero_id = :h "
                              "AND round_no = :r AND status IN ('draft','confirmed') AND id != :i"),
                         {"s": sid, "h": hero_id, "r": session["round_no"], "i": action_id})
        await db.execute(text("UPDATE player_binding SET turn_status = 'in_group_action' WHERE session_id = :s "
                              "AND hero_id = :h AND turn_status IN ('idle','thinking')"), {"s": sid, "h": hero_id})
    await db.commit()
    heroes = content.heroes_catalog()
    name = heroes[hero_id]["name"].split()[0]
    await publish(db, sid, f"hero:{row['hero_id']}", "feed.message", {
        "kind": "system", "round": session["round_no"],
        "text": f"{name} {'идёт с тобой' if accept else 'отказывается'}."})


async def speak(db: AsyncSession, session: dict[str, Any], hero_id: str, line: str) -> None:
    """Реплика слышна только героям в той же зоне («Тебя слышат»)."""
    sid = session["id"]
    heroes = content.heroes_catalog()
    me = await world.hero_row(db, sid, hero_id)
    msg = {"kind": "speech", "round": session["round_no"], "from": hero_id,
           "text": f"{heroes[hero_id]['name'].split()[0]}: «{line}»"}
    for h in await world.all_hero_rows(db, sid):
        if h["zone_id"] == me["zone_id"]:
            await publish(db, sid, f"hero:{h['hero_id']}", "feed.message", msg)


async def communicate(db: AsyncSession, session: dict[str, Any], hero_id: str, side: dict[str, Any]) -> dict[str, Any]:
    """Шёпот (только своя зона, без броска) и окрик (Дух, один раз за раунд, основное действие не тратит)."""
    sid = session["id"]
    scenario = world.scenario_of(session)
    heroes = content.heroes_catalog()
    target = side["target_hero"]
    me = await world.hero_row(db, sid, hero_id)
    them = await world.hero_row(db, sid, target)
    myname = heroes[hero_id]["name"].split()[0]
    result = {"delivered": False}

    async def note(text_: str, hero: str = hero_id) -> None:
        await publish(db, sid, f"hero:{hero}", "feed.message", {"kind": "system", "round": session["round_no"], "text": text_})

    if not them or target == hero_id:
        await note("Некому это сказать.")
        return result
    if side["type"] == "whisper":
        if not rules.can_whisper(me["zone_id"], them["zone_id"]):
            await note("Шёпот не долетит: этот герой не рядом. Можно окликнуть.")
            return result
        fact_id = f"whisper:{uuid.uuid4().hex[:8]}"
        await add_fact(db, sid, fact_id, f"{myname} шепчет: «{side['content']}»", 1, "whisper",
                       session["round_no"], [hero_id, target])
        await publish(db, sid, f"hero:{target}", "feed.message", {
            "kind": "whisper", "round": session["round_no"], "text": f"{myname} шепчет тебе: «{side['content']}»"})
        await note(f"Ты шепчешь {heroes[target]['name'].split()[0]}: «{side['content']}»")
        return {"delivered": True}

    # окрик
    used = await world.row(db, "SELECT id FROM dice_roll WHERE session_id = :s AND hero_id = :h AND round_no = :r "
                               "AND kind = 'shout'", s=sid, h=hero_id, r=session["round_no"])
    if used:
        await note("Окликнуть можно только один раз за раунд.")
        return result
    distance = rules.zone_distance(scenario["adjacency"], me["zone_id"], them["zone_id"])
    if distance is None or distance < 1:
        await note("Окрик нужен для другой зоны. Тому, кто рядом, можно прошептать.")
        return result
    dc = rules.shout_dc(distance, scenario.get("time") == "night")
    spirit = me["stats"]["spirit"] + rules.total_wound_penalty(world.wound_objects(
        await world.wounds(db, sid, hero_id)))
    roll = get_roller().roll_d20(spirit, dc)
    await db.execute(
        text("INSERT INTO dice_roll (session_id, round_no, hero_id, kind, stat, natural, modifier, difficulty, outcome) "
             "VALUES (:s, :r, :h, 'shout', 'spirit', :n, :m, :dc, :o)"),
        {"s": sid, "r": session["round_no"], "h": hero_id, "n": roll.natural, "m": spirit, "dc": dc,
         "o": roll.outcome.value})
    await db.commit()
    await publish(db, sid, "all", "roll.public", {
        "hero_id": hero_id, "hero_name": heroes[hero_id]["name"], "kind": "shout", "label": "Окрик (Дух)",
        "natural": roll.natural, "modifier": spirit, "dc": dc, "outcome": roll.outcome.value})
    heard = roll.outcome in (rules.Outcome.MINIMAL_SUCCESS, rules.Outcome.SUCCESS, rules.Outcome.GREAT_SUCCESS)
    if heard:
        line = side["content"] if roll.outcome != rules.Outcome.MINIMAL_SUCCESS else side["content"][:40] + "…"
        await publish(db, sid, f"hero:{target}", "feed.message", {
            "kind": "shout", "round": session["round_no"], "text": f"{myname} кричит: «{line}»"})
        await note("Тебя услышали.")
    else:
        await note("Крик потонул в ночи: никто не расслышал.")
    return {"delivered": heard}


async def arrive(db: AsyncSession, session: dict[str, Any], hero_id: str, zone: str) -> None:
    """Герой вошёл в зону: она открывается ему и всем, а первое посещение локации запускает её часы."""
    sid = session["id"]
    scenario = world.scenario_of(session)
    loc = content.zone_to_location(scenario)[zone]
    await db.execute(text("INSERT OR IGNORE INTO hero_zone_visit (session_id, hero_id, zone_id) VALUES (:s, :h, :z)"),
                     {"s": sid, "h": hero_id, "z": zone})
    await db.execute(text("UPDATE zone_state SET visited = 1 WHERE session_id = :s AND zone_id = :z"), {"s": sid, "z": zone})
    await db.execute(text("UPDATE location SET visited_by_any = 1, discovered = 1 WHERE session_id = :s AND id = :l"),
                     {"s": sid, "l": loc})
    await db.execute(text("UPDATE hero_state SET zone_id = :z, location_id = :l, pending_zone = NULL "
                          "WHERE session_id = :s AND hero_id = :h"), {"s": sid, "h": hero_id, "z": zone, "l": loc})
    await db.commit()


async def move_hero(db: AsyncSession, session: dict[str, Any], hero_id: str, zone: str) -> str:
    """Свободный шаг в соседнюю зону. Между локациями герой приходит в конце раунда."""
    sid = session["id"]
    scenario = world.scenario_of(session)
    hs = await world.hero_row(db, sid, hero_id)
    if zone == hs["zone_id"]:
        return "stay"
    if zone not in scenario["adjacency"].get(hs["zone_id"], []):
        raise SagaError("action_unavailable", "Туда нельзя пройти за один шаг")
    zone_loc = content.zone_to_location(scenario)
    if zone_loc[zone] != hs["location_id"]:
        heroes = await world.all_hero_rows(db, sid)
        occupied = {h["location_id"] for h in heroes}
        last = sum(1 for h in heroes if h["location_id"] == hs["location_id"]) == 1
        if not rules.can_open_location(occupied, zone_loc[zone], leaving_last=last):
            raise SagaError("action_unavailable", "Все 5 мест заняты. Сначала кто-то должен вернуться")
    if _cross_link(scenario, hs["zone_id"], zone):
        await db.execute(text("UPDATE hero_state SET pending_zone = :z WHERE session_id = :s AND hero_id = :h"),
                         {"z": zone, "s": sid, "h": hero_id})
        await db.commit()
        await publish(db, sid, f"hero:{hero_id}", "feed.message", {
            "kind": "system", "round": session["round_no"], "text": "Ты доберёшься туда в конце раунда."})
        return "pending"
    await arrive(db, session, hero_id, zone)
    return "moved"
