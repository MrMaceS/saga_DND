from engine import rules


def filter_for_hero(facts: list[dict], hero_id: str) -> list[dict]:
    """Возвращает только факты, которые знает герой."""
    return rules.visible_facts(facts, hero_id)


def can_share(fact: dict, sender: str, recipients: list[str], zones: dict[str, str]) -> bool:
    """Проверяет, может ли отправитель передать факт получателям."""
    if sender not in fact.get("known_by", []):
        return False
    sender_zone = zones.get(sender)
    return all(zones.get(r) == sender_zone for r in recipients)


def share(fact: dict, sender: str, recipients: list[str], zones: dict[str, str]) -> dict:
    """Передаёт факт, возвращает обновлённую копию."""
    return rules.share_fact(fact, sender, recipients, zones)