"""Данные сценариев. Идентификаторы C-xx соответствуют docs/TEST_PLAN.md."""
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCEN = yaml.safe_load((ROOT / "data" / "scenarios" / "ship_without_crew.yaml").read_text(encoding="utf-8"))
ALLOWED_LEVELS = {10, 12, 14, 16}
TERRAIN_TYPES = {"position", "height", "fire", "entangle"}


def all_zones():
    return {z for loc in SCEN["locations"].values() for z in loc["zones"]}


def test_zones_and_adjacency_are_consistent():
    zones = all_zones()
    assert set(SCEN["adjacency"]) == zones
    for a, neighbours in SCEN["adjacency"].items():
        for b in neighbours:
            assert b in zones
            assert a in SCEN["adjacency"][b], f"связь {a}-{b} не симметрична"
    assert set(SCEN["zone_names"]) == zones
    assert SCEN["start_zone"] in zones


def test_cross_location_links_point_to_different_locations():
    zone_loc = {z: k for k, loc in SCEN["locations"].items() for z in loc["zones"]}
    for link in SCEN["cross_location_links"]:
        assert zone_loc[link["from"]] != zone_loc[link["to"]]
        assert link["to"] in SCEN["adjacency"][link["from"]]


def test_tasks_reference_valid_zones_and_clocks():
    clocks = {c["id"] for c in SCEN["clocks"]}
    for t in SCEN["tasks"]:
        assert t["zone"] in all_zones()
        assert set(t["levels"]) == {1, 2, 3}
        assert all(text.strip() for text in t["levels"].values())
        if "ignored_clock" in t:
            assert t["ignored_clock"] in clocks
        assert set(t["chip_phrases"]) <= {1, 2, 3}


def test_hints_do_not_reveal_secret_names():
    for t in SCEN["tasks"]:
        for level in (1, 2):
            text = t["levels"][level]
            for secret in SCEN["secret_names"]:
                assert secret not in text, f"{t['id']} уровень {level} выдаёт «{secret}»"
    # а на уровне 3 раскрытие допустимо
    assert "Тьёдвар" in SCEN["tasks"][0]["levels"][3]


def test_chip_phrases_do_not_name_unknown_things():
    # Подсказка уровня 1 говорит словами героя и не называет скрытое.
    for t in SCEN["tasks"]:
        phrase = t["chip_phrases"].get(1, "")
        for secret in SCEN["secret_names"]:
            assert secret not in phrase


def test_clocks_are_valid():
    tasks = {t["id"] for t in SCEN["tasks"]}
    cutscenes = {c["id"] for c in SCEN["cutscenes"]}
    for c in SCEN["clocks"]:
        assert c["location"] in SCEN["locations"]
        assert 0 <= c["start"] < c["segments"]
        assert c["task"] in tasks
        if "cutscene_on_full" in c:
            assert c["cutscene_on_full"] in cutscenes
        for at, cs in c.get("cutscene_at", {}).items():
            assert 0 < at < c["segments"] and cs in cutscenes


def test_enemy_roster_is_fixed_and_does_not_scale_with_players():
    assert SCEN["scaling"] == "none"
    assert len(SCEN["enemies"]) == 3
    for e in SCEN["enemies"]:
        assert e["level"] in ALLOWED_LEVELS and e["cells"] >= 1
        assert e["zone"] in all_zones()
        assert not any("player" in key for key in e)
    assert SCEN["joins_combat_when"]["clock"] in {c["id"] for c in SCEN["clocks"]}


def test_range_allows_two_to_ten_players():
    assert SCEN["allowed_players"] == [2, 10]
    lo, hi = SCEN["recommended_players"]
    assert 2 <= lo <= hi <= 10


def test_terrain_and_npcs_are_placed_in_real_zones():
    for obj in SCEN["terrain"]:
        assert obj["zone"] in all_zones() and obj["type"] in TERRAIN_TYPES and obj["names"]
    for npc in SCEN["npcs"]:
        assert npc["zone"] in all_zones() and npc["attitude"] == "neutral"   # старт всегда нейтральный


def test_roll_tables_use_known_clocks_and_all_outcomes():
    clocks = {c["id"] for c in SCEN["clocks"]}
    for name, table in SCEN["rolls"].items():
        for outcome, result in table["outcomes"].items():
            assert outcome in {"great_success", "success", "minimal_success", "fail",
                               "fail_with_consequence", "critical_fail"}
            assert set(result.get("clocks", {})) <= clocks
    assert "info_level" in SCEN["rolls"]["check_hold"]["outcomes"]["minimal_success"]
    assert SCEN["rolls"]["check_hold"]["outcomes"]["minimal_success"]["info_level"] == 1


def test_views_match_info_levels_of_known_zones():
    for zone, levels in SCEN["views"].items():
        assert zone in all_zones()
        assert set(levels) <= {1, 2, 3}


def test_cutscenes_have_audio_ids_in_assets_plan():
    plan = (ROOT / "docs" / "offline_assets_plan.md").read_text(encoding="utf-8")
    for c in SCEN["cutscenes"]:
        assert c["id"] in plan, f"{c['id']} нет в offline_assets_plan.md"


def test_aliases_point_to_real_zones():
    for zone, words in SCEN["zone_aliases"].items():
        assert zone in all_zones() and words
