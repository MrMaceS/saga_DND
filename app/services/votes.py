"""Голосования: настройки вечера (в БД), выход из игры и пропуск кат-сцены (в памяти, живут недолго)."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.services import world
from app.services.sync import publish
from app.ws.hub import hub
from engine import rules

ALLOWED = {"reader_mode": {"off", "rotate", "volunteers"}, "cruelty": {"restrained", "bloody"},
           "ambience": {"on", "off"}}
RULE_KEY = {"reader_mode": "reader", "cruelty": "cruelty", "ambience": "ambience"}

_memory: dict[tuple[str, str], dict[str, bool]] = {}


async def propose_setting(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], key: str, value: str) -> None:
    if session["status"] != "lobby":
        raise SagaError("invalid_state", "Настройки вечера меняются до начала саги")
    if key not in ALLOWED or value not in ALLOWED[key]:
        raise SagaError("invalid_state", "Неизвестная настройка")
    if not player["hero_id"]:
        raise SagaError("forbidden", "Сначала выберите героя")
    sid = session["id"]
    if world.settings_of(session).get(key) == value:
        return
    await db.execute(text("UPDATE setting_vote SET status = 'rejected' WHERE session_id = :s AND key = :k AND status = 'open'"),
                     {"s": sid, "k": key})
    await db.execute(text("INSERT INTO setting_vote (session_id, key, value, proposer, votes_json) "
                          "VALUES (:s, :k, :v, :p, :j)"),
                     {"s": sid, "k": key, "v": value, "p": player["hero_id"], "j": json.dumps({player["hero_id"]: True})})
    await db.commit()
    await _evaluate_setting(db, session)


async def cast_setting_vote(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], vote_id: int, agree: bool) -> None:
    vote = await world.row(db, "SELECT * FROM setting_vote WHERE id = :i AND session_id = :s AND status = 'open'",
                           i=vote_id, s=session["id"])
    if not vote or not player["hero_id"]:
        raise SagaError("not_found", "Голосование не найдено")
    votes = json.loads(vote["votes_json"])
    votes[player["hero_id"]] = agree
    await db.execute(text("UPDATE setting_vote SET votes_json = :j WHERE id = :i"), {"j": json.dumps(votes), "i": vote_id})
    await db.commit()
    await _evaluate_setting(db, session)


async def _evaluate_setting(db: AsyncSession, session: dict[str, Any]) -> None:
    sid = session["id"]
    total = len(await SessionRepository(db).players(sid))
    for v in await world.rows(db, "SELECT * FROM setting_vote WHERE session_id = :s AND status = 'open'", s=sid):
        rule = rules.SETTING_VOTE_RULE[RULE_KEY[v["key"]]]
        verdict = rules.vote_passes(rule, json.loads(v["votes_json"]), total)
        if verdict is None:
            continue
        status = "passed" if verdict else "rejected"
        await db.execute(text("UPDATE setting_vote SET status = :st WHERE id = :i"), {"st": status, "i": v["id"]})
        if verdict:
            current = await world.row(db, "SELECT settings_json FROM game_session WHERE id = :s", s=sid)
            settings = json.loads(current["settings_json"])
            settings[v["key"]] = v["value"]
            await db.execute(text("UPDATE game_session SET settings_json = :j WHERE id = :s"),
                             {"j": json.dumps(settings), "s": sid})
        await db.commit()


async def set_volunteer(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], on: bool) -> None:
    if world.settings_of(session).get("reader_mode") != "volunteers":
        raise SagaError("invalid_state", "Режим «Добровольцы» не выбран")
    await db.execute(text("UPDATE player_binding SET is_reader = :v WHERE session_id = :s AND device_token = :t"),
                     {"v": int(on), "s": session["id"], "t": player["device_token"]})
    await db.commit()


# --------------------------- кратковременные голосования (в памяти)
def _eligible(session_id: str) -> int:
    return len({c.hero_id for c in hub.hands.values() if c.session_id == session_id and c.hero_id})


async def start_exit_vote(db: AsyncSession, session: dict[str, Any]) -> None:
    _memory[(session["id"], "exit")] = {}
    await publish(db, session["id"], "all", "vote.request", {"kind": "exit", "text": "Сохранить и выйти?"})


async def cast_memory_vote(db: AsyncSession, session: dict[str, Any], player: dict[str, Any], kind: str, agree: bool) -> bool | None:
    key = (session["id"], kind)
    if key not in _memory:
        raise SagaError("not_found", "Голосование не начато")
    _memory[key][player["hero_id"]] = agree
    rule = "unanimous" if kind == "exit" else "majority"
    verdict = rules.vote_passes(rule, _memory[key], _eligible(session["id"]))
    if verdict is not None:
        del _memory[key]
    return verdict


def start_skip_vote(session_id: str) -> None:
    _memory.setdefault((session_id, "skip"), {})
