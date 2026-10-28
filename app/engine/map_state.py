"""Карты и туман войны. Чистые функции: данные приходят снаружи, имена зон берутся из сценария."""
from typing import Any

from engine import rules


class LocationStatus:
    UNKNOWN = "unknown"
    RUMOR = "rumor"
    SCOUTED = "scouted"
    VISITED = "visited"


def compute_status(visited: bool, scouted_level: int, rumored: bool) -> str:
    return rules.location_state(visited, scouted_level, rumored)


def clock_visibility(location_active: bool, info_level: int, filled: int, segments: int) -> dict:
    return rules.clock_view(location_active, info_level, filled, segments)


def visible_zone_ids(visited: set[str], adjacency: dict[str, list[str]],
                     extra: set[str] | None = None) -> set[str]:
    """Видны посещённые зоны, их соседи и зоны известных задач (всё это рисуется как «?»)."""
    visible = set(visited) | set(extra or ())
    for zone in visited:
        visible.update(adjacency.get(zone, []))
    return visible


def _zones_payload(scenario: dict[str, Any], visited: set[str],
                   extra: set[str] | None = None) -> tuple[list[dict], dict[str, list[str]]]:
    adjacency = scenario["adjacency"]
    visible = visible_zone_ids(visited, adjacency, extra)
    layout = scenario.get("layout", {})
    zones = []
    for zone_id in scenario["adjacency"]:
        if zone_id not in visible:
            continue
        is_visited = zone_id in visited
        zones.append({
            "id": zone_id,
            # Имя отдаётся только если зона посещена. Иначе клиент рисует «?».
            "name": scenario["zone_names"][zone_id] if is_visited else None,
            "visible": True,
            "visited": is_visited,
            "x": layout.get(zone_id, [None, None])[0],
            "y": layout.get(zone_id, [None, None])[1],
        })
    filtered = {z["id"]: [n for n in adjacency[z["id"]] if n in visible] for z in zones}
    return zones, filtered


def build_table_map(scenario: dict[str, Any], visited_zones: set[str], clocks: list[dict[str, Any]],
                    active_locations: set[str], task_levels: dict[str, int],
                    hero_zones: dict[str, str] | None = None) -> dict[str, Any]:
    """Общая карта Стола.

    clocks: [{id, location_id, filled, segments}]; уровень часов берётся по их задаче (task_levels).
    Часы неразведанной угрозы и часы непосещённой локации вообще не попадают в ответ.
    """
    known_task_zones = {t["zone"] for t in scenario["tasks"] if task_levels.get(t["id"], 0) >= 1}
    zones, adjacency = _zones_payload(scenario, visited_zones, known_task_zones)
    clock_meta = {c["id"]: c for c in scenario["clocks"]}
    clocks_out = []
    for clock in clocks:
        meta = clock_meta.get(clock["id"], {})
        level = task_levels.get(meta.get("task", ""), 0)
        view = rules.clock_view(clock["location_id"] in active_locations, level, clock["filled"], clock["segments"])
        if not view["visible"]:
            continue
        named = view.get("named", False)
        clocks_out.append({
            "id": clock["id"],
            "location_id": clock["location_id"],
            "name": meta.get("name") if named else None,
            "icon": meta.get("icon"),
            "named": named,
            "stage": view.get("stage") or rules.clock_stage(clock["filled"], clock["segments"]),
            # Без разведки цифры не раскрываются.
            "filled": clock["filled"] if named else None,
            "segments": clock["segments"] if named else None,
        })
    return {"zones": zones, "adjacency": adjacency, "clocks": clocks_out,
            "heroes": [{"hero_id": h, "zone_id": z} for h, z in (hero_zones or {}).items() if z in
                       {zone["id"] for zone in zones}]}


def build_personal_map(scenario: dict[str, Any], hero_id: str, visited_zones: set[str], current_zone: str,
                       heroes_here: list[str], known_task_zones: set[str] | None = None) -> dict[str, Any]:
    """Личная карта героя: имена только у зон, где побывал именно он."""
    zones, adjacency = _zones_payload(scenario, visited_zones | {current_zone}, known_task_zones)
    for z in zones:
        z["current"] = z["id"] == current_zone
    return {"hero_id": hero_id, "zones": zones, "adjacency": adjacency, "current_zone": current_zone,
            "heroes_here": heroes_here}


def build_view_from_zone(zone_id: str, zone_name: str, description: str | None) -> dict[str, Any]:
    return {"zone_id": zone_id, "zone_name": zone_name,
            "description": description or f"Вы находитесь в зоне {zone_name}."}


def build_chips_for_hero(hero_id: str, known_tasks: list[dict[str, Any]], simple_pool: list[str],
                         rotation: int = 0, max_story: int = 3) -> dict[str, Any]:
    return rules.build_chips(known_tasks, hero_id, simple_pool, rotation, max_story)
