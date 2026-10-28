"""Тесты загрузчика сценария."""
from pathlib import Path
import pytest
from app.engine.scene import ScenarioLoader, ScenarioValidationError


SCENARIOS_DIR = Path(__file__).resolve().parent.parent / "data" / "scenarios"


def test_load_ship_without_crew():
    """Сценарий загружается и проходит валидацию."""
    loader = ScenarioLoader(SCENARIOS_DIR)
    scenario = loader.load("ship_without_crew")
    assert scenario.id == "ship_without_crew"
    assert scenario.title == "Корабль без команды"
    assert "locations" in scenario.data


def test_load_nonexistent_scenario():
    """Несуществующий сценарий вызывает ошибку."""
    loader = ScenarioLoader(SCENARIOS_DIR)
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent")


def test_validate_asymmetric_adjacency(tmp_path):
    """Несимметричная смежность отвергается."""
    yaml_content = """
id: test
title: Тест
scaling: none
allowed_players: [2, 10]
recommended_players: [2, 6]
start_zone: a
secret_names: []
locations:
  loc: {name: Локация, zones: [a, b]}
adjacency:
  a: [b]
  b: []
cross_location_links: []
zone_names: {a: А, b: Б}
zone_aliases: {a: [], b: []}
tasks: []
clocks: []
enemies: []
npcs: []
terrain: []
views: {}
rolls: {}
cutscenes: []
"""
    path = tmp_path / "test.yaml"
    path.write_text(yaml_content, encoding="utf-8")
    loader = ScenarioLoader(tmp_path)
    with pytest.raises(ScenarioValidationError, match="не симметрична"):
        loader.load("test")


def test_validate_secret_in_hint(tmp_path):
    """Подсказка уровня 1-2 не должна раскрывать секрет."""
    yaml_content = """
id: test
title: Тест
scaling: none
allowed_players: [2, 10]
recommended_players: [2, 6]
start_zone: a
secret_names: [Секрет]
locations:
  loc: {name: Локация, zones: [a]}
adjacency: {a: []}
cross_location_links: []
zone_names: {a: А}
zone_aliases: {a: []}
tasks:
  - id: task1
    zone: a
    title: Задача
    levels: {1: Здесь Секрет, 2: Продолжение, 3: Финал}
    chip_phrases: {}
clocks: []
enemies: []
npcs: []
terrain: []
views: {}
rolls: {}
cutscenes: []
"""
    path = tmp_path / "test.yaml"
    path.write_text(yaml_content, encoding="utf-8")
    loader = ScenarioLoader(tmp_path)
    with pytest.raises(ScenarioValidationError, match="раскрывает секрет"):
        loader.load("test")