"""Интерпретатор действий игроков: Gemini со структурным выводом, проверкой по контексту и повторами."""
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.ai.client import AIClient, AIClientError
from app.ai.fallback import interpreter_fallback
from app.ai.schemas import InterpreterResponse

logger = logging.getLogger(__name__)

_INTERPRETER_PROMPT = (
    Path(__file__).resolve().parent.parent.parent / "prompts" / "interpreter_system.md"
).read_text(encoding="utf-8")
MAX_ATTEMPTS = 3


def build_interpreter_context(hero_id: str, known_zones: list[str], zone_aliases: dict[str, list[str]],
                              known_tasks: list[dict[str, Any]], visible_enemies: list[dict[str, Any]],
                              visible_terrain: list[dict[str, Any]], items: list[str], abilities: list[str],
                              hero_positions: dict[str, str], **extra: Any) -> dict[str, Any]:
    """Контекст ТОЛЬКО из того, что знает герой (скрытые зоны и факты сюда не попадают)."""
    context = {
        "hero_id": hero_id, "zones": known_zones, "zone_aliases": zone_aliases, "tasks": known_tasks,
        "enemies": visible_enemies, "terrain": visible_terrain, "items": items, "abilities": abilities,
        "others_in_scene": [{"id": hid, "zone": zone} for hid, zone in hero_positions.items() if hid != hero_id],
    }
    context.update(extra)
    return context


def validate_against_context(result: dict[str, Any], context: dict[str, Any]) -> list[str]:
    """Проверка id по контексту героя. Пустой список = всё в порядке."""
    errors: list[str] = []
    zones = set(context.get("zones", []))
    task_ids = {t["id"] for t in context.get("tasks", []) if "id" in t}
    hero_ids = {o["id"] for o in context.get("others_in_scene", [])}
    for field in ("target_zone", "requires_move_to"):
        if result.get(field) and zones and result[field] not in zones:
            errors.append(f"{field}={result[field]!r} нет в списке известных зон")
    if result.get("target_task") and context.get("tasks") is not None and result["target_task"] not in task_ids:
        # неразведанная задача не существует для героя
        if task_ids or context.get("tasks") == []:
            errors.append(f"target_task={result['target_task']!r} героем не обнаружена")
    for hero in [result.get("target_hero"), *(result.get("needs_consent_from") or [])]:
        if hero and hero_ids and hero not in hero_ids:
            errors.append(f"герой {hero!r} не найден")
    side = result.get("side_action")
    if side and hero_ids and side.get("target_hero") not in hero_ids:
        errors.append(f"side_action.target_hero={side.get('target_hero')!r} не найден")
    return errors


async def interpret_action(client: AIClient, model: str, hero_id: str, raw_text: str,
                           context: dict[str, Any]) -> dict[str, Any]:
    """Возвращает проверенный разбор действия. После трёх неудач работает офлайн-интерпретатор."""
    base_prompt = (f"КОНТЕКСТ СЦЕНЫ:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
                   f"Игрок пишет: {raw_text}")
    schema = InterpreterResponse.model_json_schema()
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = await client.generate(model=model, system_prompt=_INTERPRETER_PROMPT,
                                        user_prompt=base_prompt + feedback, temperature=0.0,
                                        response_schema=schema)
            validated = InterpreterResponse(**raw).model_dump()
            validated["hero_id"] = hero_id  # подмена hero_id невозможна
            problems = validate_against_context(validated, context)
            if not problems:
                return validated
            feedback = "\n\nОшибка предыдущего ответа: " + "; ".join(problems) + ". Исправь и верни JSON."
            logger.warning("Интерпретатор, попытка %s: %s", attempt, problems)
        except AIClientError as e:
            logger.error("Интерпретатор недоступен: %s", e)
            break
        except (ValidationError, TypeError, ValueError) as e:
            feedback = f"\n\nОшибка схемы предыдущего ответа: {str(e)[:300]}. Верни корректный JSON."
            logger.warning("Интерпретатор, попытка %s, схема: %s", attempt, e)
    return interpreter_fallback(context, raw_text)
