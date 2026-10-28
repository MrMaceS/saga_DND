from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml


class ScenarioValidationError(Exception):
    """Ошибка валидации сценария."""
    pass


@dataclass
class Scenario:
    """Загруженный и валидированный сценарий."""
    id: str
    title: str
    data: dict[str, Any]


class ScenarioLoader:
    """Загрузчик сценариев из data/scenarios/."""

    def __init__(self, scenarios_dir: Path):
        self.scenarios_dir = scenarios_dir

    def load(self, scenario_id: str) -> Scenario:
        """Загрузить и валидировать сценарий."""
        path = self.scenarios_dir / f"{scenario_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Сценарий не найден: {scenario_id}")

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        self._validate(raw)
        return Scenario(id=raw["id"], title=raw["title"], data=raw)

    def _validate(self, data: dict[str, Any]) -> None:
        """Валидация сценария (повторяет проверки из tests/test_scenarios.py)."""
        # C-01: зоны и смежность
        zones = {z for loc in data["locations"].values() for z in loc["zones"]}
        if set(data["adjacency"]) != zones:
            raise ScenarioValidationError("Смежность не покрывает все зоны")
        for a, neighbours in data["adjacency"].items():
            for b in neighbours:
                if b not in zones:
                    raise ScenarioValidationError(f"Зона {b} не существует")
                if a not in data["adjacency"][b]:
                    raise ScenarioValidationError(f"Связь {a}-{b} не симметрична")
        if set(data["zone_names"]) != zones:
            raise ScenarioValidationError("zone_names не покрывает все зоны")
        if data["start_zone"] not in zones:
            raise ScenarioValidationError("start_zone не существует")

        # C-02: ссылки между локациями
        zone_loc = {z: k for k, loc in data["locations"].items() for z in loc["zones"]}
        for link in data["cross_location_links"]:
            if zone_loc[link["from"]] == zone_loc[link["to"]]:
                raise ScenarioValidationError("cross_location_links внутри одной локации")
            if link["to"] not in data["adjacency"][link["from"]]:
                raise ScenarioValidationError(f"cross_location_links {link['from']}-{link['to']} не в смежности")

        # C-03: задачи
        clocks = {c["id"] for c in data["clocks"]}
        for t in data["tasks"]:
            if t["zone"] not in zones:
                raise ScenarioValidationError(f"Задача {t['id']} ссылается на несуществующую зону")
            if set(t["levels"]) != {1, 2, 3}:
                raise ScenarioValidationError(f"Задача {t['id']} должна иметь уровни 1, 2, 3")
            if "ignored_clock" in t and t["ignored_clock"] not in clocks:
                raise ScenarioValidationError(f"Задача {t['id']} ссылается на несуществующие часы")

        # C-04: подсказки не раскрывают секреты
        for t in data["tasks"]:
            for level in (1, 2):
                text = t["levels"][level]
                for secret in data["secret_names"]:
                    if secret in text:
                        raise ScenarioValidationError(f"Подсказка уровня {level} раскрывает секрет {secret}")

        # C-05: часы
        tasks = {t["id"] for t in data["tasks"]}
        cutscenes = {c["id"] for c in data["cutscenes"]}
        for c in data["clocks"]:
            if c["location"] not in data["locations"]:
                raise ScenarioValidationError(f"Часы {c['id']} ссылаются на несуществующую локацию")
            if not (0 <= c["start"] < c["segments"]):
                raise ScenarioValidationError(f"Часы {c['id']}: start должен быть < segments")
            if c["task"] not in tasks:
                raise ScenarioValidationError(f"Часы {c['id']} ссылаются на несуществующую задачу")
            if "cutscene_on_full" in c and c["cutscene_on_full"] not in cutscenes:
                raise ScenarioValidationError(f"Часы {c['id']}: cutscene_on_full не существует")

        # C-06: враги
        if data["scaling"] != "none":
            raise ScenarioValidationError("scaling должен быть 'none'")
        allowed_levels = {10, 12, 14, 16}
        for e in data["enemies"]:
            if e["level"] not in allowed_levels:
                raise ScenarioValidationError(f"Враг {e['id']}: недопустимый уровень {e['level']}")
            if e["zone"] not in zones:
                raise ScenarioValidationError(f"Враг {e['id']} размещён в несуществующей зоне")

        # C-07: диапазон игроков
        if data["allowed_players"] != [2, 10]:
            raise ScenarioValidationError("allowed_players должен быть [2, 10]")

        # C-08: местность и NPC
        terrain_types = {"position", "height", "fire", "entangle"}
        for obj in data["terrain"]:
            if obj["zone"] not in zones:
                raise ScenarioValidationError(f"Местность {obj['id']} в несуществующей зоне")
            if obj["type"] not in terrain_types:
                raise ScenarioValidationError(f"Местность {obj['id']}: недопустимый тип {obj['type']}")
        for npc in data["npcs"]:
            if npc["zone"] not in zones:
                raise ScenarioValidationError(f"NPC {npc['id']} в несуществующей зоне")
            if npc["attitude"] != "neutral":
                raise ScenarioValidationError(f"NPC {npc['id']} должен начинаться с attitude='neutral'")

        # C-09: таблицы бросков
        for name, table in data["rolls"].items():
            for outcome in table["outcomes"]:
                if outcome not in {"great_success", "success", "minimal_success", "fail", "fail_with_consequence", "critical_fail"}:
                    raise ScenarioValidationError(f"Таблица {name}: недопустимый исход {outcome}")

        # C-10: виды
        for zone in data["views"]:
            if zone not in zones:
                raise ScenarioValidationError(f"Вид для несуществующей зоны {zone}")

        # C-11: псевдонимы
        for zone in data["zone_aliases"]:
            if zone not in zones:
                raise ScenarioValidationError(f"Псевдоним для несуществующей зоны {zone}")


def get_scenario_loader() -> ScenarioLoader:
    """Получить загрузчик сценариев."""
    scenarios_dir = Path(__file__).resolve().parent.parent.parent / "data" / "scenarios"
    return ScenarioLoader(scenarios_dir)