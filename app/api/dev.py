"""Отладочные эндпоинты. Работают только при DEV=1."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.client import metrics
from app.ai.service import get_ai_client
from app.config import settings
from app.domain.errors import SagaError
from app.engine import dice_provider

router = APIRouter(prefix="/api/dev", tags=["dev"])


def _require_dev() -> None:
    if not settings.dev:
        raise SagaError("forbidden", "Только при DEV=1")


class DiceBody(BaseModel):
    values: list[int]


@router.get("/ai-stats")
async def ai_stats():
    _require_dev()
    return {**metrics.to_dict(), "ai_enabled": settings.ai_enabled, "models": {
        "interpreter": settings.model_interpreter, "narrator": settings.model_narrator}}


@router.post("/dice")
async def set_dice(body: DiceBody):
    _require_dev()
    dice_provider.set_preset(body.values)
    return {"preset": body.values}


@router.get("/ai-ping")
async def ai_ping():
    """Проверка связи с Gemini: один короткий запрос, время ответа."""
    _require_dev()
    client = get_ai_client()
    if client is None:
        return {"ok": False, "reason": "GEMINI_API_KEY не задан, работает офлайн-режим"}
    import time
    start = time.monotonic()
    try:
        out = await client.generate(model=settings.model_interpreter, system_prompt="Ответь JSON {\"ok\": true}",
                                    user_prompt="ping", temperature=0.0,
                                    response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}})
        return {"ok": True, "model": settings.model_interpreter, "ms": round((time.monotonic() - start) * 1000), "reply": out}
    except Exception as e:
        return {"ok": False, "model": settings.model_interpreter, "error": str(e)[:300]}
