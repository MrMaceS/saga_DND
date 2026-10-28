"""Тесты логики карт и тумана."""
import pytest
from app.engine.map_state import build_personal_map, build_table_map, build_view_from_zone, build_chips_for_hero


def test_personal_map_shows_only_visited_and_neighbors():
    """Личная карта показывает только посещённые зоны и их соседей."""
    result = build_personal_map(
        hero_id="astrid",
        all_zones=["deck", "hold", "mast", "pier", "rocks"],
        visited_zones={"pier"},
        known_zones={"pier", "deck"},
        adjacency={
            "deck": ["pier", "hold", "mast"],
            "hold": ["deck"],
            "mast": ["deck"],
            "pier": ["deck", "rocks"],
            "rocks": ["pier"],
        },
    )

    zones_by_id = {z["id"]: z for z in result["zones"]}

    # Пирс посещён
    assert zones_by_id["pier"]["visited"] is True
    assert zones_by_id["pier"]["name"] == "pier"

    # Палуба — сосед пирса, видна, но не посещена
    assert zones_by_id["deck"]["visible"] is True
    assert zones_by_id["deck"]["visited"] is False
    assert zones_by_id["deck"]["name"] == "???"

    # Скалы — сосед пирса, видна
    assert zones_by_id["rocks"]["visible"] is True
    assert zones_by_id["rocks"]["visited"] is False

    # Трюм и мачта — не соседи пирса, не видны
    assert zones_by_id["hold"]["visible"] is False
    assert zones_by_id["mast"]["visible"] is False


def test_table_map_shows_all_visited_zones():
    """Общая карта показывает все посещённые зоны."""
    result = build_table_map(
        all_zones=["deck", "hold", "pier"],
        visited_zones={"pier", "deck"},
        adjacency={"deck": ["pier", "hold"], "pier": ["deck"], "hold": ["deck"]},
        clocks=[{"id": "c1", "zone": "hold", "filled": 1, "segments": 3}],
        active_locations={"ship"},
        info_levels={"hold": 1},
    )

    zones_by_id = {z["id"]: z for z in result["zones"]}

    assert zones_by_id["pier"]["visited"] is True
    assert zones_by_id["deck"]["visited"] is True
    assert zones_by_id["hold"]["visible"] is False  # Не посещена


def test_table_map_clock_visibility():
    """Часы на общей карте видны только если info_level >= 2."""
    result = build_table_map(
        all_zones=["hold", "rocks"],
        visited_zones=set(),
        adjacency={},
        clocks=[
            # ИСПРАВЛЕНИЕ: добавили поле "location", чтобы оно совпадало с active_locations
            {"id": "c1", "zone": "hold", "location": "ship", "filled": 1, "segments": 3},
            {"id": "c2", "zone": "rocks", "location": "shore", "filled": 2, "segments": 6},
        ],
        active_locations={"ship", "shore"},
        info_levels={"hold": 1, "rocks": 2},
    )

    clocks_by_id = {c["id"]: c for c in result["clocks"]}

    # hold: info_level=1, виден только намёк (stage)
    assert "c1" in clocks_by_id
    assert clocks_by_id["c1"]["hint"] is not None
    assert clocks_by_id["c1"]["filled"] is None  # Цифры скрыты

    # rocks: info_level=2, видны цифры
    assert "c2" in clocks_by_id
    assert clocks_by_id["c2"]["filled"] == 2
    assert clocks_by_id["c2"]["segments"] == 6


def test_view_from_zone_returns_description():
    """«Вид» из зоны возвращает описание."""
    result = build_view_from_zone(
        zone_id="pier",
        zone_name="Пирс",
        description="Здесь пахнет смолой.",
    )

    assert result["zone_id"] == "pier"
    assert result["zone_name"] == "Пирс"
    assert "смолой" in result["description"]


def test_chips_for_hero_returns_known_tasks():
    """Подсказки для героя включают известные задачи."""
    result = build_chips_for_hero(
        hero_id="astrid",
        known_tasks=[
            {
                "id": "check_hold",
                "zone": "hold",
                "level": 1,
                "known_by": ["astrid"],  # <-- ИСПРАВЛЕНИЕ: добавили это поле
                "phrases": {1: "Прислушаться к стуку"},
                "updated_round": 2,
            }
        ],
        simple_pool=["Осмотреться", "Отдохнуть"],
        rotation=0,
        max_story=3,
    )

    assert "story" in result
    assert "simple" in result
    assert len(result["story"]) > 0
    assert "Прислушаться к стуку" in result["story"][0]