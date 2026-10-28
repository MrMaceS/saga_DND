import json
import logging
from pathlib import Path
from typing import Any

from app.ai.client import AIClient, AIClientError
from app.ai.schemas import NarratorResponse
from app.ai.fallback import narrator_fallback

logger = logging.getLogger(__name__)
BANNED_WORDS = ("движок", "бросок", "кубик", "сложность", "характеристик")

_NARRATOR_PROMPT = (
    Path(__file__).resolve().parent.parent.parent / "prompts" / "narrator_system.md"
).read_text(encoding="utf-8")


def build_narrator_input(
    outcome: str,
    effects: list[str],
    revealed: list[str],
    clocks_changed: dict[str, int],
    hero_profile: dict[str, Any],
    scene_facts: list[str],
    enemy_facts: list[str],
    cruelty: str = "restrained",
) -> dict[str, Any]:
    """Строит вход для диктора. Скрытая правда НЕ передаётся."""
    return {
        "outcome": outcome,
        "effects": effects,
        "revealed": revealed,
        "clocks_changed": clocks_changed,
        "hero_profile": hero_profile,
        "scene_facts": scene_facts,
        "enemy_facts": enemy_facts,
        "cruelty": cruelty,
    }


async def narrate(
    client: AIClient,
    model: str,
    engine_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Вызывает диктора для описания результата.
    Возвращает NarratorResponse или fallback.
    """
    user_prompt = json.dumps(engine_result, ensure_ascii=False, indent=2)
    schema = NarratorResponse.model_json_schema()

    feedback = ""
    for attempt in range(1, 4):
        try:
            result = await client.generate(model=model, system_prompt=_NARRATOR_PROMPT,
                                           user_prompt=user_prompt + feedback, temperature=0.9,
                                           response_schema=schema)
            validated = NarratorResponse(**result).model_dump()
            banned = [w for w in BANNED_WORDS if w in validated["public"].lower()]
            if not banned:
                return validated
            feedback = f"\n\nОшибка: нельзя употреблять слова {banned}. Перепиши."
        except AIClientError as e:
            logger.error("Narrator failed: %s", e)
            break
        except Exception as e:  # невалидный JSON / схема: повтор с пояснением
            feedback = f"\n\nОшибка схемы: {str(e)[:200]}. Верни корректный JSON."
            logger.warning("Narrator attempt %s: %s", attempt, e)
    return narrator_fallback(engine_result)