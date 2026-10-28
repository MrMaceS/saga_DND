"""Запасные тексты. Работают без сети и без ключа Gemini."""
import json
import random
from pathlib import Path
from typing import Any

_FALLBACK_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fallback_narration"


def _load(name: str) -> dict[str, Any]:
    path = _FALLBACK_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


_GENERIC = _load("generic.json")
_EXPLORATION = _load("exploration.json")


def interpreter_fallback(context: dict[str, Any], raw_text: str) -> dict[str, Any]:
    """Офлайн-интерпретатор (по словам из сценария). Нужен, если Gemini недоступен или ключа нет."""
    from app.ai.local_interpreter import interpret_local
    return interpret_local(raw_text, context)


def narrator_fallback(engine_result: dict[str, Any], rng: random.Random | None = None) -> dict[str, Any]:
    """Диктор без ИИ: шаблон по исходу, раскрытое уходит герою, часы описываются образно."""
    rng = rng or random.Random()
    hero = engine_result.get("hero_profile", {}) or {}
    name = (hero.get("name") or "Герой").split()[0]
    hero_id = hero.get("id") or ""
    outcome = engine_result.get("outcome") or ""

    templates = (_EXPLORATION.get("outcomes", {}).get(outcome)
                 or _GENERIC.get("templates") or ["Сцена продолжается."])
    public = rng.choice(templates).format(hero=name, intent=engine_result.get("intent", ""))

    for line in engine_result.get("clock_phrases", []):
        public = f"{public} {line}."

    private: dict[str, str] = {}
    revealed = engine_result.get("revealed") or []
    if hero_id and revealed:
        private[hero_id] = f"{name}, ты узнаёшь: " + "; ".join(r.rstrip('.') for r in revealed) + "."
    return {"public": public, "private": private}
