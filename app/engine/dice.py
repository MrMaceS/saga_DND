import random
from dataclasses import dataclass
from engine import rules


@dataclass(frozen=True)
class DiceRoll:
    """Результат одного броска."""
    natural: int          # 1..20 для d20, 1..6 для d6
    modifier: int
    dc: int
    outcome: rules.Outcome


class DiceRoller:
    """Бросает кубики. RNG передаётся снаружи для тестируемости."""

    def __init__(self, rng: random.Random | None = None, preset: list[int] | None = None):
        """
        rng: генератор случайных чисел (по умолчанию SystemRandom).
        preset: фиксированная последовательность значений для тестов.
                Если задана, броски берут первые N значений из preset.
        """
        self._rng = rng or random.SystemRandom()
        self._preset = list(preset) if preset else None
        self._preset_idx = 0

    def _next_value(self, sides: int) -> int:
        if self._preset is not None:
            if self._preset_idx >= len(self._preset):
                raise RuntimeError("preset исчерпан")
            value = self._preset[self._preset_idx]
            self._preset_idx += 1
            if not 1 <= value <= sides:
                raise ValueError(f"preset значение {value} вне диапазона 1..{sides}")
            return value
        return self._rng.randint(1, sides)

    def roll_d20(self, modifier: int, dc: int) -> DiceRoll:
        natural = self._next_value(20)
        outcome = rules.roll_outcome(natural, modifier, dc)
        return DiceRoll(natural=natural, modifier=modifier, dc=dc, outcome=outcome)

    def roll_d6(self) -> int:
        return self._next_value(6)

    def roll_check(
        self,
        stat: int,
        wound_mod: int,
        base: str,
        tags: list[str],
    ) -> DiceRoll:
        """Полная проверка: d20 + stat + wound_mod против сложности."""
        dc = rules.compute_difficulty(base, tags)
        total_mod = stat + wound_mod
        return self.roll_d20(total_mod, dc)