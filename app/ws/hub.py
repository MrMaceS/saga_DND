"""Менеджер WebSocket-подключений: Стол (по сессии) и Руки (по токену устройства)."""
import logging
from dataclasses import dataclass

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class HandConn:
    ws: WebSocket
    session_id: str
    hero_id: str | None


class Hub:
    def __init__(self) -> None:
        self.tables: dict[str, list[WebSocket]] = {}
        self.hands: dict[str, HandConn] = {}  # device_token -> соединение
        self.busy = 0  # сколько обработчиков отключения ещё работает (нужно для аккуратной остановки)

    def reset(self) -> None:
        self.tables.clear()
        self.hands.clear()
        self.busy = 0

    # --- регистрация ---
    def add_table(self, session_id: str, ws: WebSocket) -> None:
        self.tables.setdefault(session_id, []).append(ws)

    def add_hand(self, token: str, session_id: str, hero_id: str | None, ws: WebSocket) -> None:
        self.hands[token] = HandConn(ws, session_id, hero_id)

    def remove_table(self, session_id: str, ws: WebSocket) -> None:
        if ws in self.tables.get(session_id, []):
            self.tables[session_id].remove(ws)

    def remove_hand(self, token: str, ws: WebSocket) -> None:
        conn = self.hands.get(token)
        if conn and conn.ws is ws:
            del self.hands[token]

    def set_hero(self, token: str, hero_id: str | None) -> None:
        if token in self.hands:
            self.hands[token].hero_id = hero_id

    def hand_tokens(self, session_id: str) -> list[str]:
        return [t for t, c in self.hands.items() if c.session_id == session_id]

    def is_connected(self, session_id: str, hero_id: str) -> bool:
        return any(c.session_id == session_id and c.hero_id == hero_id for c in self.hands.values())

    # --- отправка ---
    async def _send(self, ws: WebSocket, message: dict) -> bool:
        try:
            await ws.send_json(message)
            return True
        except Exception as e:  # соединение разорвано
            logger.info("ws send failed: %s", e)
            return False

    async def send_table(self, session_id: str, message: dict) -> None:
        for ws in list(self.tables.get(session_id, [])):
            if not await self._send(ws, message):
                self.remove_table(session_id, ws)

    async def send_token(self, token: str, message: dict) -> None:
        conn = self.hands.get(token)
        if conn and not await self._send(conn.ws, message):
            self.remove_hand(token, conn.ws)

    async def send_hero(self, session_id: str, hero_id: str, message: dict) -> None:
        for token, conn in list(self.hands.items()):
            if conn.session_id == session_id and conn.hero_id == hero_id:
                await self.send_token(token, message)

    async def send_all(self, session_id: str, message: dict) -> None:
        await self.send_table(session_id, message)
        for token in self.hand_tokens(session_id):
            await self.send_token(token, message)


hub = Hub()
manager = hub  # обратная совместимость имени
