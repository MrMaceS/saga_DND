"""Фильтрация состояния для конкретного героя («клиент получает только то, что знает его герой»)."""
from engine import rules


def build_hand_payload(hero_id: str, full_state: dict) -> dict:
    return {
        "hero_id": hero_id,
        "facts": rules.visible_facts(full_state.get("facts", []), hero_id),
    }
