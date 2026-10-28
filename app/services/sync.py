"""Рассылка: журнал событий (seq) и актуальные состояния Столу и рукам."""
import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import SessionRepository
from app.services import state
from app.ws.hub import hub

_locks: dict[str, asyncio.Lock] = {}


def session_lock(session_id: str) -> asyncio.Lock:
    """Мутации сессии выполняются по одной: порядок раундов не ломается при одновременных нажатиях."""
    return _locks.setdefault(session_id, asyncio.Lock())


def _message(type_: str, seq: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": type_, "seq": seq, "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "payload": payload}


async def publish(db: AsyncSession, session_id: str, audience: str, type_: str, payload: dict[str, Any]) -> int:
    """Пишет событие в журнал и отправляет адресатам. audience: table | all | hero:<id>."""
    res = await db.execute(
        text("INSERT INTO ws_event (session_id, audience, type, payload_json) VALUES (:s, :a, :t, :p)"),
        {"s": session_id, "a": audience, "t": type_, "p": json.dumps(payload, ensure_ascii=False)})
    seq = res.lastrowid
    await db.commit()
    msg = _message(type_, seq, payload)
    if audience == "table":
        await hub.send_table(session_id, msg)
    elif audience == "all":
        await hub.send_all(session_id, msg)
    elif audience.startswith("hero:"):
        await hub.send_hero(session_id, audience.split(":", 1)[1], msg)
    return seq


async def push_states(db: AsyncSession, session_id: str) -> None:
    """Отправляет свежие состояния: Столу общее, каждой руке своё (с фильтрацией знаний)."""
    repo = SessionRepository(db)
    res = await db.execute(text("SELECT * FROM game_session WHERE id = :s"), {"s": session_id})
    row = res.fetchone()
    if not row:
        return
    session = dict(row._mapping)
    connected = {c.hero_id for c in hub.hands.values() if c.session_id == session_id and c.hero_id}
    if hub.tables.get(session_id):
        table_state = await state.build_table_state(db, session, connected)
        await hub.send_table(session_id, _message("table.state", 0, table_state))
    for token in hub.hand_tokens(session_id):
        player = await repo.player_by_token(session_id, token)
        if not player:
            continue
        hub.set_hero(token, player["hero_id"])
        hand_state = await state.build_hand_state(db, session, player)
        await hub.send_token(token, _message("hero.state", 0, hand_state))


async def replay_since(db: AsyncSession, session_id: str, audiences: tuple[str, ...], last_seq: int) -> list[dict[str, Any]]:
    placeholders = ",".join(f":a{i}" for i in range(len(audiences)))
    params = {f"a{i}": a for i, a in enumerate(audiences)}
    res = await db.execute(
        text(f"SELECT id, type, payload_json FROM ws_event WHERE session_id = :s AND id > :l "
             f"AND audience IN ({placeholders}) ORDER BY id"), {"s": session_id, "l": last_seq, **params})
    return [_message(r.type, r.id, json.loads(r.payload_json)) for r in res.fetchall()]
