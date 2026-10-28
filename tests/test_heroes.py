"""Данные героев. Идентификаторы H-xx соответствуют docs/TEST_PLAN.md."""
import json
from pathlib import Path

import pytest

DATA = json.loads((Path(__file__).resolve().parent.parent / "data" / "heroes.json").read_text(encoding="utf-8"))
HEROES = DATA["heroes"]
ENDURANCE = {"ragnar": 3, "astrid": 5, "eirik": 4, "sigrid": 2, "vald": 2, "gunnhild": 2,
             "torvald": 3, "bjorn": 4, "leif": 3, "helga": 2, "halldora": 5}
STATS = ("strength", "agility", "wits", "spirit")
REQUIRED = ["id", "name", "title", "stats", "endurance", "gift", "action_ability", "minor_ability",
            "weakness", "goal", "secrets", "start_items", "growth", "interrogation"]


def test_there_are_eleven_unique_heroes():
    ids = [h["id"] for h in HEROES]
    assert len(ids) == 11 and len(set(ids)) == 11
    assert set(ids) == set(ENDURANCE)


@pytest.mark.parametrize("hero", HEROES, ids=lambda h: h["id"])
def test_hero_is_complete_and_balanced(hero):
    for key in REQUIRED:
        assert key in hero, f"{hero['id']}: нет поля {key}"
    stats = hero["stats"]
    assert set(stats) == set(STATS)
    assert sum(stats.values()) == DATA["rules"]["stat_sum"] == 9
    assert all(1 <= v <= 4 for v in stats.values())
    assert hero["endurance"] == ENDURANCE[hero["id"]]
    assert hero["minor_ability"]["once_per"] == "scene"
    assert set(hero["secrets"]) == {"story", "personal"}
    assert len(hero["goal"]["steps"]) == 3
    assert len(hero["growth"]) == 2 and len(hero["start_items"]) >= 2
    assert hero["action_ability"]["name"] and hero["gift"]["name"] and hero["weakness"]["name"]


def test_endurance_roughly_follows_strength():
    # Устойчивость не должна расходиться с Силой больше чем на 2 (защита от опечаток в данных).
    for h in HEROES:
        assert abs(h["endurance"] - (h["stats"]["strength"] + 1)) <= 2


def test_only_gunnhild_and_helga_can_return_from_beyond():
    can = {h["id"] for h in HEROES if h.get("rescue", {}).get("return_from_beyond")}
    assert can == {"gunnhild", "helga"}


def test_everyone_starts_without_wounds_in_rules():
    assert DATA["rules"]["growth_per_evening"] == 1
    assert DATA["rules"]["wound_penalty_cap"] == -5
    assert DATA["rules"]["inventory_slots"] == 4


def test_team_covers_all_four_stats_at_four():
    top = {s for h in HEROES for s, v in h["stats"].items() if v == 4}
    assert top == set(STATS)
