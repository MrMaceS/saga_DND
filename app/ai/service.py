"""Выбор ИИ-клиента: Gemini при наличии ключа, иначе офлайн-режим (клиент None)."""
from app.ai.client import AIClient, GeminiClient
from app.config import settings

_client: AIClient | None = None
_override: AIClient | None = None  # подмена в тестах


def get_ai_client() -> AIClient | None:
    global _client
    if _override is not None:
        return _override
    if not settings.ai_enabled:
        return None
    if _client is None:
        _client = GeminiClient()
    return _client


def set_ai_client_for_tests(client: AIClient | None) -> None:
    global _override
    _override = client
