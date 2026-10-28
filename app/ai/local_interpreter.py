"""Офлайн-интерпретатор свободного текста. Работает по словам сценария (zone_aliases, подсказки задач).

Нужен как запасной режим, когда Gemini недоступен или ключ не задан. Возвращает ту же структуру,
что и ИИ-интерпретатор (InterpreterResponse), и видит только то, что знает герой.
"""
import re
from typing import Any

COMBAT = ("бью", "бить", "ударю", "ударить", "атак", "стреля", "убью", "убить", "рублю", "душу", "пленю", "сража", "дерусь")
WAIT = ("жду", "ждём", "ждем", "подожд", "ничего не дел", "наблюда", "стою на месте")
INVESTIGATE = ("осмотр", "провер", "обыск", "прислуш", "слуш", "изуч", "ищу", "поищ", "найти", "исслед",
               "загляну", "смотрю", "гляжу", "разгляд", "осматр", "разузна", "выясн")
MOVE = ("иду", "пойду", "иди", "перейд", "вхожу", "зайду", "поднимусь", "спущусь", "бегу", "вернусь", "возвращ", "иду")
SHOUT = ("кричу", "крикну", "окрик", "ору", "зову", "позову", "позвать", "кричать")
WHISPER = ("шепч", "шепн", "шепот")
TALK = ("говорю", "скажу", "сказать", "спрошу", "спрашиваю", "отвечаю", "приказываю")
PROPOSE = ("прошу", "попрошу", "предлагаю", "пойдём", "пойдем", "давай", "зову", "позову")
ITEM = ("использую", "беру", "зажигаю", "поджигаю", "бросаю", "достаю", "привязываю")
CAREFUL = ("осторожн", "тихо", "незаметн", "аккуратн", "крадусь")
RUSHED = ("быстро", "бегом", "спешу", "срочно")

SIMPLE_SUGGESTIONS = ["Осмотреться", "Прислушаться", "Подождать"]


def _has(text: str, stems: tuple[str, ...]) -> bool:
    return any(s in text for s in stems)


def _stem(word: str) -> str:
    word = word.lower().strip()
    return word[:-1] if len(word) > 4 else word


def _mentions(text: str, words: list[str]) -> bool:
    tokens = re.findall(r"[а-яёa-z0-9]+", text)
    return any(tok.startswith(_stem(w)) for w in words if w for tok in tokens)


def _result(hero_id: str, action_type: str, intent: str, stat: str, **extra: Any) -> dict[str, Any]:
    base = {
        "hero_id": hero_id, "action_type": action_type, "target_zone": None, "target_task": None,
        "target_hero": None, "target_item": None, "intent": intent, "required_stat": stat, "base": "normal",
        "difficulty_tags": [], "resources_required": [], "uses_ability": None, "trigger_condition": None,
        "requires_move_to": None, "side_action": None, "free_actions": [], "needs_consent_from": [],
        "needs_clarification": False, "clarifying_question": None, "is_possible": True,
        "rejection_reason": None, "alternative": None,
    }
    base.update(extra)
    return base


def interpret_local(raw_text: str, context: dict[str, Any]) -> dict[str, Any]:
    hero_id = context.get("hero_id", "unknown")
    text = " ".join(raw_text.lower().split())
    current_zone = context.get("current_zone")
    aliases: dict[str, list[str]] = context.get("zone_aliases", {})
    zone_names: dict[str, str] = context.get("zone_names", {})
    tasks: list[dict[str, Any]] = context.get("tasks", [])
    others: list[dict[str, Any]] = context.get("others_in_scene", [])
    items = context.get("items", [])
    item_names = [i if isinstance(i, str) else " ".join(i.get("names", [])) for i in items]

    def clarify(question: str) -> dict[str, Any]:
        sugg = [t["phrases"][t["level"]] for t in tasks
                if t.get("level", 0) >= 1 and t["level"] in t.get("phrases", {})][:3] + SIMPLE_SUGGESTIONS[:1]
        return _result(hero_id, "wait", raw_text, "wits", needs_clarification=True,
                       clarifying_question=question, alternative=sugg[0] if sugg else None)

    if not text:
        return clarify("Что делает герой?")

    if _has(text, COMBAT):
        return _result(hero_id, "combat", raw_text, "strength")

    # --- цели ---
    target_hero = next((o["id"] for o in others
                        if _mentions(text, [o["id"], *o.get("names", [])]) and o["id"] != hero_id), None)
    zone = None
    for zone_id in context.get("zones", []):
        words = list(aliases.get(zone_id, [])) + ([zone_names[zone_id]] if zone_id in zone_names else [])
        if _mentions(text, words):
            zone = zone_id
            break
    task = None
    if zone:
        task = next((t for t in tasks if t.get("zone") == zone and t.get("level", 0) >= 1), None)
    if task is None and zone is None:  # если зона названа явно, задачу по словам подсказок не угадываем
        for t in tasks:
            phrase_words = " ".join(t.get("phrases", {}).values()).lower().split()
            # глаголы в неопределённой форме («проверить», «следить») не опознают задачу, только существительные
            keys = [w for w in phrase_words if len(w) > 4 and not w.endswith(("ть", "ться"))]
            if keys and _mentions(text, keys) and t.get("level", 0) >= 1:
                task = t
                zone = zone or t.get("zone")
                break

    tags = []
    if _has(text, CAREFUL):
        tags.append("careful")
    if _has(text, RUSHED):
        tags.append("rushed")
    if "факел" in text and any("факел" in n for n in item_names):
        tags.append("prepared")

    side = None
    if target_hero and _has(text, WHISPER):
        side = {"type": "whisper", "target_hero": target_hero, "content": raw_text}
    elif target_hero and _has(text, SHOUT):
        side = {"type": "shout", "target_hero": target_hero, "content": raw_text}

    wants_move = _has(text, MOVE)
    wants_look = _has(text, INVESTIGATE)
    asks = target_hero is not None and _has(text, PROPOSE)

    # Основное действие
    explicit = wants_look or wants_move or asks
    if zone and (explicit or (task and side is None)):
        stat = "wits"
        action = "investigate" if (wants_look or task or asks) else "move"
        if _has(text, CAREFUL) and not wants_look and not task:
            action, stat = "sneak", "agility"
        if action == "move":
            stat = "agility"
        main = _result(hero_id, action, raw_text, stat, target_zone=zone,
                       target_task=task["id"] if task else None, difficulty_tags=tags,
                       requires_move_to=zone if zone != current_zone else None, side_action=side)
        if target_hero and asks:
            main["needs_consent_from"] = [target_hero]
        return main

    if target_hero and asks and not _has(text, WHISPER):
        t = task["id"] if task else None
        return _result(hero_id, "propose", raw_text, "spirit", target_hero=target_hero, target_task=t,
                       needs_consent_from=[target_hero], side_action=side)

    if side:
        return _result(hero_id, "wait", raw_text, "spirit", side_action=side, target_hero=target_hero)

    if wants_look:
        here = next((t for t in tasks if t.get("zone") == current_zone and t.get("level", 0) >= 1), None)
        return _result(hero_id, "investigate", raw_text, "wits", target_zone=current_zone,
                       target_task=here["id"] if here else None, difficulty_tags=tags)

    if _has(text, ITEM):
        return _result(hero_id, "use_item", raw_text, "agility")

    if _has(text, WAIT):
        return _result(hero_id, "wait", raw_text, "wits")

    if _has(text, TALK):
        return _result(hero_id, "talk", raw_text, "spirit", free_actions=[raw_text])

    return clarify("Что именно делает герой? Опишите действие чуть подробнее.")
