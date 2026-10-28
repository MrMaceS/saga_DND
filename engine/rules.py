"""Эталонная реализация базовых правил «Саги Мьёльнира».

Чистые функции без ввода-вывода: кубик, состояние и сеть передаются снаружи.
Константы вынесены наверх, чтобы баланс правился в одном месте.
Число игроков НЕ участвует ни в одной формуле сложности (это правило игры).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

# ---------------------------------------------------------------- константы
BASE_DC = {"easy": 9, "normal": 11, "hard": 14}
TAG_MODS = {
    # условия мира (добавляет сервер)
    "dark": 1, "no_light": 1, "fog": 1, "alone": 2, "with_partner": -1,
    # подход (определяет интерпретатор)
    "prepared": -1, "careful": -1, "rushed": 1, "noisy": 1,
}
DC_MIN, DC_MAX = 5, 25

WOUND_PENALTY_CAP = -5
MAX_STRIKES_PER_ROUND = 3
MAX_OCCUPIED_LOCATIONS = 5
DEFEND_BONUS = 2           # «Защититься» всегда чуть надёжнее контратаки
SHOUT_BASE_DC = 8
DYING_CLOCK_START = 3
MAX_INFO_LEVEL = 3
ALLY_INFO_CAP = 2

SELF_HEAL_BASE_DC = {"light": 8, "medium": 12, "heavy": 16}
NO_KIT_PENALTY = 4
RESCUE_DC = {"drag": 10, "drag_armored": 12, "stabilize": 10, "return_from_beyond": 14}

# Правила голосования: кто решает.
SETTING_VOTE_RULE = {
    "reader": "majority", "ambience": "majority", "cruelty": "unanimous",
    "save_and_exit": "unanimous", "skip_cutscene": "majority",
}

AUTO_READY_STATUSES = {"downed", "unconscious", "ai", "away"}


# ------------------------------------------------------------ проверка d20
class Outcome(str, Enum):
    CRITICAL_FAIL = "critical_fail"
    FAIL_WITH_CONSEQUENCE = "fail_with_consequence"
    FAIL = "fail"
    MINIMAL_SUCCESS = "minimal_success"
    SUCCESS = "success"
    GREAT_SUCCESS = "great_success"


def _check_d20(natural: int) -> None:
    if not 1 <= natural <= 20:
        raise ValueError(f"d20 вне диапазона: {natural}")


def roll_outcome(natural: int, modifier: int, dc: int) -> Outcome:
    """d20 + модификатор против сложности (единая таблица исходов)."""
    _check_d20(natural)
    if natural == 1:
        return Outcome.CRITICAL_FAIL
    if natural == 20:
        return Outcome.GREAT_SUCCESS
    diff = natural + modifier - dc
    if diff >= 8:
        return Outcome.GREAT_SUCCESS
    if diff >= 3:
        return Outcome.SUCCESS
    if diff >= 0:
        return Outcome.MINIMAL_SUCCESS
    if diff >= -4:
        return Outcome.FAIL
    return Outcome.FAIL_WITH_CONSEQUENCE


def compute_difficulty(base: str, tags: Sequence[str]) -> int:
    """Сложность = база + теги. Числа игроков здесь нет сознательно."""
    if base not in BASE_DC:
        raise ValueError(f"неизвестная база: {base}")
    unknown = [t for t in tags if t not in TAG_MODS]
    if unknown:
        raise ValueError(f"неизвестные теги: {unknown}")
    dc = BASE_DC[base] + sum(TAG_MODS[t] for t in set(tags))
    return max(DC_MIN, min(DC_MAX, dc))


# ------------------------------------------------------------------ раны
class Severity(str, Enum):
    LIGHT = "light"
    MEDIUM = "medium"
    HEAVY = "heavy"


class BodyPart(str, Enum):
    HEAD = "head"
    TORSO = "torso"
    ARM = "arm"
    LEG = "leg"


_ORDER = [Severity.LIGHT, Severity.MEDIUM, Severity.HEAVY]
_CELLS = {Severity.LIGHT: 1, Severity.MEDIUM: 1, Severity.HEAVY: 2}
_PENALTY = {Severity.LIGHT: -1, Severity.MEDIUM: -2, Severity.HEAVY: -3}
AFFECTED_STATS = {
    BodyPart.HEAD: ("wits", "spirit"), BodyPart.TORSO: ("strength",),
    BodyPart.ARM: ("weapon_and_craft",), BodyPart.LEG: ("agility", "movement"),
}


@dataclass(frozen=True)
class Wound:
    severity: Severity
    body_part: BodyPart

    @property
    def cells(self) -> int:
        return _CELLS[self.severity]

    @property
    def penalty(self) -> int:
        return _PENALTY[self.severity]


def severity_from_shortfall(shortfall: int, natural: int = 10) -> Severity | None:
    """Насколько не хватило до сложности. 1-4 лёгкое, 5-9 среднее, 10+ или натуральная 1 тяжёлое."""
    if natural == 1:
        return Severity.HEAVY
    if shortfall <= 0:
        return None
    if shortfall <= 4:
        return Severity.LIGHT
    if shortfall <= 9:
        return Severity.MEDIUM
    return Severity.HEAVY


def escalate(sev: Severity, steps: int = 1) -> Severity:
    return _ORDER[min(_ORDER.index(sev) + steps, len(_ORDER) - 1)]


def deescalate(sev: Severity) -> Severity | None:
    i = _ORDER.index(sev)
    return None if i == 0 else _ORDER[i - 1]


def adjust_for_body_part(sev: Severity, part: BodyPart) -> Severity:
    """Голова и торс на ступень тяжелее."""
    return escalate(sev) if part in (BodyPart.HEAD, BodyPart.TORSO) else sev


def body_part_from_d6(d6: int) -> BodyPart:
    """Решение по умолчанию: 1 голова, 2-3 торс, 4-5 рука, 6 нога."""
    if not 1 <= d6 <= 6:
        raise ValueError(f"d6 вне диапазона: {d6}")
    return {1: BodyPart.HEAD, 2: BodyPart.TORSO, 3: BodyPart.TORSO,
            4: BodyPart.ARM, 5: BodyPart.ARM, 6: BodyPart.LEG}[d6]


def total_wound_penalty(wounds: Sequence[Wound]) -> int:
    return max(WOUND_PENALTY_CAP, sum(w.penalty for w in wounds))


def cells_used(wounds: Sequence[Wound]) -> int:
    return sum(w.cells for w in wounds)


def is_downed(used_cells: int, endurance: int) -> bool:
    return used_cells >= endurance


# ------------------------------------------------------------------- бой
@dataclass(frozen=True)
class DefenseResult:
    parried: bool
    wound: Wound | None


@dataclass(frozen=True)
class CounterResult:
    success: bool
    enemy_cells_lost: int
    wound: Wound | None


@dataclass(frozen=True)
class AttackResult:
    hit: bool
    enemy_cells_lost: int
    enemy_counterstrike: bool


def resolve_defend(natural: int, stat: int, wound_mod: int, level: int, d6: int,
                   position_bonus: int = 0) -> DefenseResult:
    """Реакция «Защититься»: d20 + лучшая из Силы/Ловкости + 2 + позиция + штраф ран против уровня врага."""
    _check_d20(natural)
    total = natural + stat + DEFEND_BONUS + position_bonus + wound_mod
    if natural == 20 or (natural != 1 and total >= level):
        return DefenseResult(True, None)
    sev = severity_from_shortfall(level - total, natural)
    assert sev is not None
    part = body_part_from_d6(d6)
    return DefenseResult(False, Wound(adjust_for_body_part(sev, part), part))


def resolve_counter(natural: int, stat: int, wound_mod: int, level: int, d6: int) -> CounterResult:
    """Реакция «Контратаковать»: успех срывает удар и бьёт в ответ, провал даёт рану на ступень тяжелее."""
    _check_d20(natural)
    margin = natural + stat + wound_mod - level
    if natural == 20 or (natural != 1 and margin >= 0):
        cells = 2 if (natural == 20 or margin >= 8) else 1
        return CounterResult(True, cells, None)
    sev = severity_from_shortfall(-margin, natural)
    assert sev is not None
    part = body_part_from_d6(d6)
    sev = escalate(adjust_for_body_part(sev, part))
    return CounterResult(False, 0, Wound(sev, part))


def resolve_attack(natural: int, stat: int, wound_mod: int, level: int, bonus: int = 0) -> AttackResult:
    """Действие «Атака/Ударить» (и атакующая местность с bonus=2)."""
    _check_d20(natural)
    margin = natural + stat + wound_mod + bonus - level
    if natural == 20 or (natural != 1 and margin >= 0):
        cells = 2 if (natural == 20 or margin >= 8) else 1
        return AttackResult(True, cells, False)
    return AttackResult(False, 0, natural == 1)


def strikes_allowed(already_received: int) -> bool:
    return already_received < MAX_STRIKES_PER_ROUND


def plan_melee(adjacency: Mapping[str, Sequence[str]], hero_zone: str, target_zone: str) -> str:
    d = zone_distance(adjacency, hero_zone, target_zone)
    if d == 0:
        return "in_zone"
    if d == 1:
        return "needs_move"
    return "impossible"


def interrogation_allowed(enemy_state: str, enemy_zone: str, hero_zone: str) -> bool:
    return enemy_state == "captive" and enemy_zone == hero_zone


# ---------------------------------------------------------------- лечение
def heal_dc(severity: Severity, self_heal: bool, has_kit: bool) -> int:
    dc = SELF_HEAL_BASE_DC[severity.value]
    return dc + (NO_KIT_PENALTY if self_heal and not has_kit else 0)


def apply_heal(sev: Severity, natural: int, total: int, dc: int) -> Severity | None:
    """None = рана исчезла. Натуральная 1 ухудшает, успех снижает на ступень."""
    _check_d20(natural)
    if natural == 1:
        return escalate(sev)
    if natural == 20 or total >= dc:
        return deescalate(sev)
    return sev


def tick_dying(clock: int) -> tuple[int, bool]:
    new = max(0, clock - 1)
    return new, new == 0


# ----------------------------------------------------------------- часы
def clock_stage(filled: int, segments: int) -> str:
    if filled * 3 < segments:
        return "quiet"
    if filled * 3 < 2 * segments:
        return "uneasy"
    return "near_doom"


def clock_view(location_active: bool, info_level: int, filled: int, segments: int) -> dict:
    """Что видит Стол: ничего, безымянное кольцо с тремя стадиями или часы с цифрами."""
    if not location_active or info_level <= 0:
        return {"visible": False}
    if info_level == 1:
        return {"visible": True, "named": False, "stage": clock_stage(filled, segments)}
    return {"visible": True, "named": True, "filled": filled, "segments": segments}


def tick_clocks(clocks: Sequence[dict], active_locations: set[str]) -> tuple[list[dict], list[str]]:
    """Конец раунда: часы активных локаций продвигаются на 1. Возвращает новые часы и id заполнившихся сейчас."""
    out, newly_full = [], []
    for c in clocks:
        c = dict(c)
        if (c["location"] in active_locations and not c.get("resolved", False)
                and c["filled"] < c["segments"]):
            c["filled"] += 1
            if c["filled"] == c["segments"]:
                newly_full.append(c["id"])
        out.append(c)
    return out, newly_full


# ---------------------------------------------------- зоны и связь
def zone_distance(adjacency: Mapping[str, Sequence[str]], a: str, b: str) -> int | None:
    if a == b:
        return 0
    seen, queue = {a}, deque([(a, 0)])
    while queue:
        zone, d = queue.popleft()
        for nxt in adjacency.get(zone, ()):
            if nxt == b:
                return d + 1
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, d + 1))
    return None


def can_whisper(zone_a: str, zone_b: str) -> bool:
    return zone_a == zone_b


def shout_dc(distance: int, noisy_or_night: bool) -> int:
    if distance < 1:
        raise ValueError("окрик нужен только для другой зоны")
    return SHOUT_BASE_DC + 2 * distance + (2 if noisy_or_night else 0)


def can_open_location(occupied: set[str], target: str, leaving_last: bool = False) -> bool:
    if target in occupied or len(occupied) < MAX_OCCUPIED_LOCATIONS:
        return True
    return leaving_last


# ------------------------------------------------ согласие и голосования
def consent_status(required: Sequence[str], responses: Mapping[str, str]) -> str:
    if any(responses.get(h) == "decline" for h in required):
        return "declined"
    if all(responses.get(h) == "accept" for h in required):
        return "confirmed"
    return "pending"


def all_ready(statuses: Mapping[str, str]) -> bool:
    if not statuses:
        return False
    return all(s == "turn_ended" or s in AUTO_READY_STATUSES for s in statuses.values())


def vote_passes(kind: str, votes: Mapping[str, bool], total_players: int) -> bool | None:
    yes = sum(1 for v in votes.values() if v)
    no = sum(1 for v in votes.values() if not v)
    if kind == "unanimous":
        if no:
            return False
        return True if yes == total_players else None
    if kind == "majority":
        if yes * 2 > total_players:
            return True
        if no * 2 >= total_players:
            return False
        return None
    raise ValueError(f"неизвестный тип голосования: {kind}")


# --------------------------------------------- знание, туман, подсказки
def visible_facts(facts: Sequence[dict], hero_id: str) -> list[dict]:
    return [f for f in facts if hero_id in f["known_by"]]


def share_fact(fact: dict, sender: str, recipients: Sequence[str], zones: Mapping[str, str]) -> dict:
    """Поделиться можно только с теми, кто в одной зоне с отправителем, и только тем, что знаешь сам."""
    if sender not in fact["known_by"]:
        raise ValueError("отправитель не знает этот факт")
    for r in recipients:
        if zones.get(r) != zones.get(sender):
            raise ValueError(f"{r} не в одной зоне с отправителем")
    new = dict(fact)
    new["known_by"] = sorted(set(fact["known_by"]) | set(recipients))
    return new


def raise_level(current: int, new: int, cap: int = MAX_INFO_LEVEL) -> int:
    """Знание не забывается: уровень только растёт."""
    return min(max(current, new), cap)


def info_gain(outcome: Outcome, is_ally: bool) -> int:
    base = {Outcome.MINIMAL_SUCCESS: 1, Outcome.SUCCESS: 2, Outcome.GREAT_SUCCESS: 3}.get(outcome, 0)
    return min(base, ALLY_INFO_CAP) if is_ally else base


def location_state(visited: bool, scouted_level: int, rumored: bool) -> str:
    if visited:
        return "visited"
    if scouted_level >= 1:
        return "scouted"
    if rumored:
        return "rumor"
    return "unknown"


def build_chips(tasks: Sequence[dict], hero_id: str, simple_pool: Sequence[str],
                rotation: int = 0, max_story: int = 3) -> dict:
    """Подсказки только из того, что герой знает, его словами. Неизвестное в подсказки не попадает."""
    known = [t for t in tasks if hero_id in t["known_by"] and t["level"] >= 1
             and t["level"] in t["phrases"]]
    known.sort(key=lambda t: t.get("updated_round", 0), reverse=True)
    story = [t["phrases"][t["level"]] for t in known[:max_story]]
    simple = simple_pool[rotation % len(simple_pool)] if simple_pool else None
    return {"story": story, "simple": simple}
