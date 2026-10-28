"""Слоты сохранений: автосохранение, ручные (3), «вечер», загрузка."""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import SagaError
from app.engine import saves
from app.services import world

MANUAL_SLOTS = 3


def _label(session: dict[str, Any], kind: str) -> str:
    prefix = {"auto": "Автосохранение", "manual": "Ручное", "evening": "Конец вечера", "crash": "Аварийное"}[kind]
    return f"{prefix}: раунд {session['round_no']}"


async def _insert(db: AsyncSession, session_id: str, kind: str, slot_no: int | None) -> int:
    session = await world.row(db, "SELECT * FROM game_session WHERE id = :s", s=session_id)
    snap = await saves.build_snapshot(session_id, db)
    res = await db.execute(
        text("INSERT INTO save_slot (session_id, kind, slot_no, label, chapter, round_no, save_version, "
             "snapshot_json, event_log_cursor) VALUES (:s, :k, :n, :l, :c, :r, :v, :j, :cur)"),
        {"s": session_id, "k": kind, "n": slot_no, "l": _label(session, kind), "c": session["chapter"],
         "r": session["round_no"], "v": saves.CURRENT_SAVE_VERSION,
         "j": json.dumps(snap, ensure_ascii=False, default=str), "cur": snap["event_log_cursor"]})
    return res.lastrowid


async def autosave(db: AsyncSession, session_id: str) -> int:
    await db.execute(text("DELETE FROM save_slot WHERE session_id = :s AND kind = 'auto'"), {"s": session_id})
    slot_id = await _insert(db, session_id, "auto", None)
    await db.commit()
    return slot_id


async def manual_save(db: AsyncSession, session_id: str, slot_no: int | None = None) -> int:
    session = await world.row(db, "SELECT round_phase FROM game_session WHERE id = :s", s=session_id)
    if session["round_phase"] != "declaring":
        raise SagaError("invalid_phase", "Диктор рассказывает, сохранение после раунда")
    used = {r["slot_no"] for r in await world.rows(
        db, "SELECT slot_no FROM save_slot WHERE session_id = :s AND kind = 'manual'", s=session_id)}
    if slot_no is None:
        free = [n for n in range(1, MANUAL_SLOTS + 1) if n not in used]
        if not free:
            raise SagaError("slots_full")
        slot_no = free[0]
    if not 1 <= slot_no <= MANUAL_SLOTS:
        raise SagaError("invalid_state", "Слот должен быть от 1 до 3")
    await db.execute(text("DELETE FROM save_slot WHERE session_id = :s AND kind = 'manual' AND slot_no = :n"),
                     {"s": session_id, "n": slot_no})
    slot_id = await _insert(db, session_id, "manual", slot_no)
    await db.commit()
    return slot_id


async def list_slots(db: AsyncSession, session_id: str) -> list[dict[str, Any]]:
    return await world.rows(
        db, "SELECT id, kind, slot_no, label, chapter, round_no, save_version, created_at FROM save_slot "
            "WHERE session_id = :s ORDER BY id DESC", s=session_id)


async def load_slot(db: AsyncSession, session_id: str, slot_id: int) -> None:
    slot = await world.row(db, "SELECT snapshot_json FROM save_slot WHERE id = :i AND session_id = :s",
                           i=slot_id, s=session_id)
    if not slot:
        raise SagaError("not_found", "Сохранение не найдено")
    await saves.apply_snapshot(session_id, json.loads(slot["snapshot_json"]), db)
