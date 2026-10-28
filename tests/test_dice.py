"""Тесты DiceRoller."""
import random
import pytest
from app.engine.dice import DiceRoller
from engine.rules import Outcome


def test_d20_uses_preset():
    roller = DiceRoller(preset=[10, 1, 20])
    r1 = roller.roll_d20(modifier=0, dc=10)
    assert r1.natural == 10
    r2 = roller.roll_d20(modifier=0, dc=10)
    assert r2.natural == 1 and r2.outcome == Outcome.CRITICAL_FAIL
    r3 = roller.roll_d20(modifier=0, dc=10)
    assert r3.natural == 20 and r3.outcome == Outcome.GREAT_SUCCESS


def test_d20_outcome_matches_rules():
    roller = DiceRoller(preset=[15])
    r = roller.roll_d20(modifier=3, dc=12)  # 15+3=18 vs 12 -> diff=6 -> SUCCESS
    assert r.outcome == Outcome.SUCCESS


def test_d6_uses_preset():
    roller = DiceRoller(preset=[4])
    assert roller.roll_d6() == 4


def test_preset_exhausted_raises():
    roller = DiceRoller(preset=[1])
    roller.roll_d20(0, 10)
    with pytest.raises(RuntimeError, match="исчерпан"):
        roller.roll_d20(0, 10)


def test_preset_out_of_range_raises():
    with pytest.raises(ValueError):
        DiceRoller(preset=[0]).roll_d20(0, 10)
    with pytest.raises(ValueError):
        DiceRoller(preset=[21]).roll_d20(0, 10)


def test_rng_is_reproducible_with_seed():
    rng1 = random.Random(42)
    rng2 = random.Random(42)
    r1 = DiceRoller(rng=rng1).roll_d20(0, 10)
    r2 = DiceRoller(rng=rng2).roll_d20(0, 10)
    assert r1.natural == r2.natural


def test_roll_check_combines_stat_and_wound():
    roller = DiceRoller(preset=[14])
    r = roller.roll_check(stat=3, wound_mod=-2, base="normal", tags=["dark"])
    # dc = 11 + 1 = 12, modifier = 3 + (-2) = 1, total = 14+1=15 vs 12 -> SUCCESS
    assert r.dc == 12
    assert r.modifier == 1
    assert r.outcome == Outcome.SUCCESS