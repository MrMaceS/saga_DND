"""Единый бросатель кубиков сервера. В DEV его можно подменить (тесты, отладка)."""
import random

from app.config import settings
from app.engine.dice import DiceRoller

_roller: DiceRoller | None = None


def get_roller() -> DiceRoller:
    global _roller
    if _roller is None:
        rng = random.Random(settings.dice_seed) if settings.dice_seed is not None else None
        _roller = DiceRoller(rng=rng)
    return _roller


def set_roller(roller: DiceRoller | None) -> None:
    global _roller
    _roller = roller


def set_preset(values: list[int]) -> None:
    set_roller(DiceRoller(preset=values))
