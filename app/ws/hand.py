"""WebSocket руки: токен устройства проверяется по БД, состояние фильтруется по герою."""
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.db.engine import async_session
from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.services import commands, rounds
from app.services.sync import push_states, replay_since, session_lock
from app.ws.hub import hub

router = APIRouter()
logger = logging.getLogger(__name__)


async def _set_status(session_id: str, token: str, status: str) -> None:
    async with async_session() as db:
        await db.execute(text("UPDATE player_binding SET status = :st WHERE session_id = :s AND device_token = :t"),
                         {"st": status, "s": session_id, "t": token})
        await db.commit()


@router.websocket("/ws/hand/{code}")
async def hand_ws(websocket: WebSocket, code: str, token: str = Query(""), last_seq: int = Query(0)):
    async with async_session() as db:
        repo = SessionRepository(db)
        session = await repo.get_session_by_code(code)
        player = await repo.player_by_token(session["id"], token) if session else None
    if not session or not player:
        await websocket.close(code=4401)
        return
    sid = session["id"]
    await websocket.accept()
    hub.add_hand(token, sid, player["hero_id"], websocket)
    await _set_status(sid, token, "active")
    async with async_session() as db:
        if last_seq:
            for event in await replay_since(db, sid, ("all", f"hero:{player['hero_id']}"), last_seq):
                await websocket.send_json(event)
        await push_states(db, sid)
    try:
        while True:
            msg = await websocket.receive_json()
            async with session_lock(sid):
                async with async_session() as db:
                    repo = SessionRepository(db)
                    fresh = await repo.get_session_by_code(code)
                    me = await repo.player_by_token(sid, token)
                    try:
                        await commands.handle_hand_message(db, fresh, me, msg)
                    except SagaError as e:
                        await db.rollback()
                        await websocket.send_json({"type": "error", "seq": 0,
                                                   "payload": {"code": e.code, "message": e.detail}})
                    await push_states(db, sid)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("hand ws failed")
    finally:
        hub.busy += 1
        try:
            hub.remove_hand(token, websocket)
            async with session_lock(sid):
                async with async_session() as db:
                    fresh = await SessionRepository(db).get_session_by_code(code)
                    if fresh and fresh["status"] == "playing":
                        await _set_status(sid, token, "away")
                        await rounds.maybe_resolve(db, sid)  # отключившийся не блокирует раунд
                    await push_states(db, sid)
        finally:
            hub.busy -= 1
