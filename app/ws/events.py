"""Модели сообщений WebSocket."""
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class WSMessage(BaseModel):
    type: str
    seq: int
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    payload: dict[str, Any]
