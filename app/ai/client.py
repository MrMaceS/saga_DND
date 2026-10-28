import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from google import genai

from app.config import settings

logger = logging.getLogger(__name__)


class AIClient(Protocol):
    """Интерфейс клиента ИИ для тестируемости."""

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


@dataclass
class AIMetrics:
    """Метрики работы ИИ."""
    total_requests: int = 0
    total_retries: int = 0
    fallback_count: int = 0
    total_time_ms: float = 0.0

    def record(self, duration_ms: float, retries: int, fallback: bool) -> None:
        self.total_requests += 1
        self.total_retries += retries
        self.total_time_ms += duration_ms
        if fallback:
            self.fallback_count += 1

    @property
    def avg_time_ms(self) -> float:
        return self.total_time_ms / self.total_requests if self.total_requests else 0.0

    @property
    def retry_rate(self) -> float:
        return self.total_retries / self.total_requests if self.total_requests else 0.0

    @property
    def fallback_rate(self) -> float:
        return self.fallback_count / self.total_requests if self.total_requests else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_retries": self.total_retries,
            "fallback_count": self.fallback_count,
            "avg_time_ms": round(self.avg_time_ms, 2),
            "retry_rate": round(self.retry_rate, 3),
            "fallback_rate": round(self.fallback_rate, 3),
        }


# Глобальный экземпляр метрик
metrics = AIMetrics()


class GeminiClient:
    """Реальный клиент Gemini с retry и timeout."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout_s: int | None = None,
        max_retries: int = 2,
    ):
        self._api_key = api_key or settings.gemini_api_key
        self._timeout_s = timeout_s or settings.ai_timeout_s
        self._max_retries = max_retries
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Генерация с retry и timeout. Выбрасывает AIClientError после всех попыток."""
        client = self._get_client()
        last_error: Exception | None = None

        for attempt in range(self._max_retries):
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._call_sync,
                        client, model, system_prompt, user_prompt, temperature, response_schema
                    ),
                    timeout=self._timeout_s,
                )
                duration_ms = (time.monotonic() - start) * 1000
                metrics.record(duration_ms, retries=attempt, fallback=False)
                return result
            except asyncio.TimeoutError as e:
                last_error = e
                logger.warning(f"Gemini timeout (attempt {attempt + 1}/{self._max_retries})")
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini error (attempt {attempt + 1}/{self._max_retries}): {e}")

        duration_ms = (time.monotonic() - start) * 1000
        metrics.record(duration_ms, retries=self._max_retries, fallback=True)
        raise AIClientError(f"Gemini failed after {self._max_retries} attempts: {last_error}")

    def _call_sync(
        self,
        client,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Синхронный вызов Gemini (обёрнут в to_thread)."""
        from google.genai import types

        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": temperature,
        }
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_json_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=config,
        )

        text = response.text
        if not text:
            raise AIClientError("Empty response from Gemini")

        if response_schema is not None:
            import json
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                raise AIClientError(f"Invalid JSON from Gemini: {e}")

        return {"text": text}


class AIClientError(Exception):
    """Ошибка клиента ИИ после всех повторов."""
    pass


class MockAIClient:
    """Мок клиента для тестов. Возвращает предзаданные ответы по порядку."""

    def __init__(self, responses: list[dict[str, Any] | Exception]):
        self._responses = list(responses)
        self._calls: list[dict[str, Any]] = []

    async def generate(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._calls.append({
            "model": model,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "temperature": temperature,
            "response_schema": response_schema,
        })
        if not self._responses:
            raise AIClientError("Mock responses exhausted")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._calls