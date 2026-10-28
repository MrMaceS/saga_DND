"""WebSocket Стола: только по токену Стола, получает общее состояние и события."""
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.db.engine import async_session
from app.db.repositories import SessionRepository
from app.services.sync import push_states, replay_since
from app.ws.hub import hub

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/table/{code}")
async def table_ws(websocket: WebSocket, code: str, token: str = Query(""), last_seq: int = Query(0)):
    async with async_session() as db:
        session = await SessionRepository(db).get_session_by_code(code)
    if not session or not token or token != session["table_token"]:
        await websocket.close(code=4401)
        return
    sid = session["id"]
    await websocket.accept()
    hub.add_table(sid, websocket)
    async with async_session() as db:
        if last_seq:
            for event in await replay_since(db, sid, ("table", "all"), last_seq):
                await websocket.send_json(event)
        await push_states(db, sid)
    try:
        while True:
            await websocket.receive_json()  # Стол только слушает; ping допускается
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("table ws failed")
    finally:
        hub.remove_table(sid, websocket)
