from dataclasses import dataclass
from engine import rules
from app.engine.dice import DiceRoller


@dataclass
class CombatResult:
    """Результат атаки или реакции."""
    success: bool
    enemy_cells_lost: int = 0
    wound: rules.Wound | None = None
    enemy_counterstrike: bool = False
    log_message: str = ""


class CombatManager:
    """Управляет боевыми взаимодействиями в раунде."""

    def __init__(self, roller: DiceRoller):
        self.roller = roller
        self.strikes_received: dict[str, int] = {}

    def resolve_hero_attack(
            self,
            hero_stat: int,
            wound_mod: int,
            enemy_level: int,
            bonus: int = 0,
    ) -> CombatResult:
        """Решает исход атаки героя по врагу (правило: равно или выше уровня врага = попадание)."""
        roll = self.roller.roll_d20(hero_stat + wound_mod + bonus, enemy_level)
        res = rules.resolve_attack(roll.natural, hero_stat, wound_mod, enemy_level, bonus)
        if res.hit:
            return CombatResult(success=True, enemy_cells_lost=res.enemy_cells_lost,
                                log_message=f"Попадание! Враг теряет {res.enemy_cells_lost} яч.")
        return CombatResult(
            success=False, enemy_counterstrike=res.enemy_counterstrike,
            log_message="Промах." + (" Враг контратакует!" if res.enemy_counterstrike else ""))

    def resolve_defend_reaction(
            self,
            hero_stat: int,
            wound_mod: int,
            enemy_level: int,
            position_bonus: int = 0,
    ) -> CombatResult:
        """Реакция «Защититься»."""
        roll = self.roller.roll_d20(hero_stat + wound_mod + position_bonus, enemy_level)
        d6 = self.roller.roll_d6()

        res = rules.resolve_defend(roll.natural, hero_stat, wound_mod, enemy_level, d6, position_bonus)

        if res.parried:
            return CombatResult(success=True, log_message="Удар успешно отбит!")
        else:
            assert res.wound is not None
            return CombatResult(
                success=False,
                wound=res.wound,
                log_message=f"Защита пробита! Получено ранение: {res.wound.severity.value} ({res.wound.body_part.value})"
            )

    def resolve_counter_reaction(
            self,
            hero_stat: int,
            wound_mod: int,
            enemy_level: int,
    ) -> CombatResult:
        """Реакция «Контратаковать»."""
        roll = self.roller.roll_d20(hero_stat + wound_mod, enemy_level)
        d6 = self.roller.roll_d6()

        res = rules.resolve_counter(roll.natural, hero_stat, wound_mod, enemy_level, d6)

        if res.success:
            return CombatResult(
                success=True,
                enemy_cells_lost=res.enemy_cells_lost,
                log_message=f"Контрудар! Вы сорвали атаку и нанесли {res.enemy_cells_lost} урона."
            )
        else:
            assert res.wound is not None
            return CombatResult(
                success=False,
                wound=res.wound,
                log_message=f"Контратака не удалась! Вы пропускаете удар и получаете ранение: {res.wound.severity.value} ({res.wound.body_part.value})"
            )

    def can_strike_hero(self, hero_id: str) -> bool:
        """Проверяет лимит в 3 удара по герою за раунд."""
        current = self.strikes_received.get(hero_id, 0)
        return rules.strikes_allowed(current)

    def register_strike(self, hero_id: str):
        self.strikes_received[hero_id] = self.strikes_received.get(hero_id, 0) + 1