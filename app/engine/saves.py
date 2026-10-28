"""Снимок и восстановление состояния сессии. Таблицы перечислены явно: новая таблица без записи здесь не сохранится."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import SagaError

CURRENT_SAVE_VERSION = 2

# Таблицы с session_id (порядок важен только для читаемости снимка)
SESSION_TABLES = [
    "player_binding", "hero_state", "injury", "location", "task", "clock", "npc", "fact", "fact_known_by",
    "zone_state", "hero_zone_visit", "action", "dice_roll", "story_event", "saga_book", "setting_vote",
    "settlement", "building", "player_note", "ws_event",
]


async def build_snapshot(session_id: str, db: AsyncSession) -> dict[str, Any]:
    res = await db.execute(text("SELECT * FROM game_session WHERE id = :id"), {"id": session_id})
    row = res.fetchone()
    if not row:
        raise SagaError("session_not_found")
    snapshot: dict[str, Any] = {"save_version": CURRENT_SAVE_VERSION, "session": dict(row._mapping), "tables": {}}
    for table in SESSION_TABLES:
        res = await db.execute(text(f"SELECT * FROM {table} WHERE session_id = :id"), {"id": session_id})
        snapshot["tables"][table] = [dict(r._mapping) for r in res.fetchall()]
    snapshot["event_log_cursor"] = max([r["id"] for r in snapshot["tables"]["ws_event"]] or [0])
    return snapshot


async def apply_snapshot(session_id: str, snapshot: dict[str, Any], db: AsyncSession) -> None:
    if snapshot.get("save_version") != CURRENT_SAVE_VERSION:
        raise SagaError("invalid_save_version",
                        f"Версия сохранения {snapshot.get('save_version')} не поддерживается "
                        f"(нужна {CURRENT_SAVE_VERSION})")
    sess = {k: v for k, v in snapshot["session"].items() if k not in ("id",)}
    assignments = ", ".join(f"{k} = :{k}" for k in sess)
    await db.execute(text(f"UPDATE game_session SET {assignments} WHERE id = :_id"), {**sess, "_id": session_id})
    for table in SESSION_TABLES:
        await db.execute(text(f"DELETE FROM {table} WHERE session_id = :id"), {"id": session_id})
        for r in snapshot["tables"].get(table, []):
            r = {**r, "session_id": session_id}
            cols = ", ".join(r)
            vals = ", ".join(f":{c}" for c in r)
            await db.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({vals})"), r)
    await db.commit()
