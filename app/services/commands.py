"""Диспетчер сообщений руки (WebSocket). Каждая команда проверяет права и фазу на сервере."""
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import SagaError
from app.engine import content
from app.services import actions, rounds, savegame, votes, world
from app.services.sync import publish
from engine import rules


async def _share_fact(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], payload: dict[str, Any]) -> None:
    sid, hero_id = session["id"], player["hero_id"]
    fact = await world.row(db, "SELECT * FROM fact WHERE session_id = :s AND id = :f", s=sid, f=payload.get("fact_id"))
    if not fact:
        raise SagaError("not_found", "Факт не найден")
    known = [r["hero_id"] for r in await world.rows(db, "SELECT hero_id FROM fact_known_by WHERE session_id = :s AND fact_id = :f",
                                                    s=sid, f=fact["id"])]
    zones = {h["hero_id"]: h["zone_id"] for h in await world.all_hero_rows(db, sid)}
    try:
        shared = rules.share_fact({"known_by": known}, hero_id, payload.get("recipients", []), zones)
    except ValueError as e:
        raise SagaError("forbidden", str(e))
    heroes = content.heroes_catalog()
    for r in set(shared["known_by"]) - set(known):
        await db.execute(text("INSERT OR IGNORE INTO fact_known_by (session_id, fact_id, hero_id) VALUES (:s, :f, :h)"),
                         {"s": sid, "f": fact["id"], "h": r})
        await publish(db, sid, f"hero:{r}", "feed.message", {
            "kind": "whisper", "round": session["round_no"],
            "text": f"{heroes[hero_id]['name'].split()[0]} делится: {fact['text']}"})
    if fact["id"].startswith("task:"):
        parts = fact["id"].split(":")
        await db.execute(text("UPDATE task SET public_level = MAX(public_level, :l) WHERE session_id = :s AND id = :t"),
                         {"l": int(parts[2]), "s": sid, "t": parts[1]})
    await db.commit()


async def handle_hand_message(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], msg: dict[str, Any]) -> None:
    kind = msg.get("type", "")
    p = msg.get("payload", {}) or {}
    hero_id = player["hero_id"]

    if kind == "ping":
        return
    if kind in ("setting.propose", "setting.vote", "reader.volunteer"):
        if kind == "setting.propose":
            await votes.propose_setting(db, session, player, p.get("key", ""), p.get("value", ""))
        elif kind == "setting.vote":
            await votes.cast_setting_vote(db, session, player, int(p.get("vote_id", 0)), bool(p.get("agree")))
        else:
            await votes.set_volunteer(db, session, player, bool(p.get("on", True)))
        return

    if session["status"] != "playing":
        raise SagaError("invalid_state", "Сага ещё не началась")
    if not hero_id:
        raise SagaError("forbidden", "У вас нет героя")

    if kind == "action.submit_text":
        await actions.submit_text(db, session, player, str(p.get("raw_text", "")))
    elif kind == "action.confirm":
        await actions.confirm_action(db, session, player, int(p.get("action_id", 0)))
    elif kind == "action.cancel":
        await actions.cancel_action(db, session, player)
    elif kind == "turn.end":
        await rounds.end_turn(db, session, player)
    elif kind == "turn.unend":
        await rounds.unend_turn(db, session, player)
    elif kind == "move.step":
        if session["round_phase"] != "declaring":
            raise SagaError("invalid_phase")
        await actions.move_hero(db, session, hero_id, str(p.get("target_zone", "")))
    elif kind in ("whisper.send", "shout.send"):
        if session["round_phase"] != "declaring":
            raise SagaError("invalid_phase")
        await actions.communicate(db, session, hero_id, {
            "type": "whisper" if kind == "whisper.send" else "shout",
            "target_hero": str(p.get("target_hero", "")), "content": str(p.get("content", ""))[:200]})
    elif kind == "consent.respond":
        await actions.consent_respond(db, session, player, int(p.get("action_id", 0)), bool(p.get("accept")))
    elif kind == "fact.share":
        await _share_fact(db, session, player, p)
    elif kind == "exit.vote":
        verdict = await votes.cast_memory_vote(db, session, player, "exit", bool(p.get("agree")))
        if verdict:
            await savegame.manual_save(db, session["id"])
            await db.execute(text("UPDATE game_session SET status = 'paused' WHERE id = :s"), {"s": session["id"]})
            await db.commit()
            await publish(db, session["id"], "all", "session.paused", {"reason": "exit"})
    elif kind == "cutscene.skip":
        votes.start_skip_vote(session["id"])
        verdict = await votes.cast_memory_vote(db, session, player, "skip", True)
        if verdict:
            await publish(db, session["id"], "table", "cutscene.skip", {})
    else:
        raise SagaError("action_unavailable", "Эта команда пока недоступна")
