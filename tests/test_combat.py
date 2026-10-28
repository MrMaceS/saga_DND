"""Сценарные тесты боя. Идентификаторы B-xx соответствуют docs/TEST_PLAN.md."""
import pytest
from engine import rules
from app.engine.dice import DiceRoller
from app.engine.combat import CombatManager


def test_B_01_combat_v8_example_astrid_rage():
    """B-01: Пример из combat_v8.md: Астрид использует Ярость (+4 к боевым проверкам)."""

    roller = DiceRoller(preset=[9])
    combat = CombatManager(roller)

    result = combat.resolve_hero_attack(
        hero_stat=4,
        wound_mod=0,
        enemy_level=12,
        bonus=4
    )

    assert result.success is True
    assert result.enemy_cells_lost == 1


def test_B_01_combat_v8_example_eirik_fire():
    """B-01: Пример из combat_v8.md: Эйрик использует местность «Огонь» (+2)."""
    roller = DiceRoller(preset=[11])
    combat = CombatManager(roller)

    result = combat.resolve_hero_attack(
        hero_stat=3,
        wound_mod=0,
        enemy_level=12,
        bonus=2
    )

    assert result.success is True
    assert result.enemy_cells_lost == 1


def test_B_02_defend_reaction_success():
    """B-02: Реакция «Защититься» успешна."""

    roller = DiceRoller(preset=[8, 4])
    combat = CombatManager(roller)

    result = combat.resolve_defend_reaction(
        hero_stat=4,
        wound_mod=0,
        enemy_level=12,
        position_bonus=0
    )

    assert result.success is True
    assert result.wound is None
    assert "отбит" in result.log_message


def test_B_02_counter_reaction_success():
    """B-02: Реакция «Контратаковать» успешна (срывает удар и бьёт в ответ)."""
    roller = DiceRoller(preset=[8, 4])
    combat = CombatManager(roller)

    result = combat.resolve_counter_reaction(
        hero_stat=4,
        wound_mod=0,
        enemy_level=12
    )

    assert result.success is True
    assert result.enemy_cells_lost == 1
    assert result.wound is None


def test_B_02_counter_reaction_failure_heavier_wound():
    """B-02: Провал контратаки даёт ранение на ступень тяжелее."""
    roller = DiceRoller(preset=[5, 4])
    combat = CombatManager(roller)

    result = combat.resolve_counter_reaction(
        hero_stat=4,
        wound_mod=0,
        enemy_level=12
    )

    assert result.success is False
    assert result.wound is not None
    assert result.wound.severity == rules.Severity.MEDIUM
    assert result.wound.body_part == rules.BodyPart.ARM


def test_B_04_cover_ally_logic():
    """B-04: «Прикрыть»: проверка, что действие тратится, но защищает союзника."""

    roller = DiceRoller()
    combat = CombatManager(roller)

    assert combat.can_strike_hero("sigrid") is True
    combat.register_strike("sigrid")
    combat.register_strike("sigrid")
    combat.register_strike("sigrid")
    assert combat.can_strike_hero("sigrid") is False

def test_B_attack_equal_to_enemy_level_is_a_hit_per_design():
    """Регрессия: «минимальный успех» (ровно или +1…+2) раньше считался промахом, а по правилам это попадание."""
    from app.engine.combat import CombatManager
    from app.engine.dice import DiceRoller
    res = CombatManager(DiceRoller(preset=[8])).resolve_hero_attack(hero_stat=4, wound_mod=0, enemy_level=12)  # 8+4 = 12
    assert res.success and res.enemy_cells_lost == 1
    miss = CombatManager(DiceRoller(preset=[5])).resolve_hero_attack(hero_stat=4, wound_mod=0, enemy_level=12)
    assert not miss.success and not miss.enemy_counterstrike
    fumble = CombatManager(DiceRoller(preset=[1])).resolve_hero_attack(hero_stat=4, wound_mod=0, enemy_level=12)
    assert fumble.enemy_counterstrike
