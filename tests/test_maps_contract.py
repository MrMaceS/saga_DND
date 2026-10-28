"""Контракт карт для фронтенда и туман войны. Идентификаторы V-03, V-04, S-13 из TEST_PLAN."""
import copy
import json

from app.engine import content, map_state
from helpers import Game


def test_maps_unavailable_before_start(client):
    g = Game(client)
    r = client.get(f"/api/maps/{g.code}/table", headers={"X-Table-Token": g.table_token})
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_state"


def test_table_map_matches_frontend_contract(client):
    g = Game(client)
    g.start()
    m = g.table_map()
    assert set(m) >= {"zones", "adjacency", "clocks"}
    for z in m["zones"]:
        assert set(z) >= {"id", "name", "visited", "visible"}
    named = {z["id"]: z["name"] for z in m["zones"]}
    assert named["pier"] == "Пирс"                         # посещённая зона названа
    assert all(named[z] is None for z in named if z != "pier")  # остальные рисуются как «?»
    for c in m["clocks"]:
        assert set(c) >= {"id", "location_id", "filled", "segments"}


def test_table_map_does_not_leak_unknown_zones_or_secrets(client):
    g = Game(client)
    g.start()
    raw = json.dumps(g.table_map(), ensure_ascii=False)
    for secret in ("cabin", "mast", "trail", "Каюта", "Мачта", "Тропа", "Трюм", "Палуба", "Тьёдвар"):
        assert secret not in raw
    # Смежность содержит только видимые зоны
    ids = {z["id"] for z in g.table_map()["zones"]}
    for a, neighbours in g.table_map()["adjacency"].items():
        assert a in ids and set(neighbours) <= ids


def test_hand_map_contract_and_names_only_for_own_visits(client):
    g = Game(client)
    g.start()
    m = g.hand_map("astrid")
    assert m["hero_id"] == "astrid" and m["current_zone"] == "pier"
    for z in m["zones"]:
        assert set(z) >= {"id", "name", "visible", "visited"}
    assert {z["id"]: z["name"] for z in m["zones"]}["pier"] == "Пирс"
    assert all(z["name"] is None for z in m["zones"] if not z["visited"])


def test_hand_map_requires_valid_device_token_and_hero(client):
    g = Game(client)
    g.start()
    assert client.get(f"/api/maps/{g.code}/hand", params={"device_token": "bad"}).status_code == 401
    assert client.get(f"/api/maps/{g.code}/table", headers={"X-Table-Token": "bad"}).status_code == 401
    assert client.get(f"/api/maps/{g.code}/table").status_code == 401


def test_clocks_unknown_threat_is_hidden_hint_is_unnamed_scouted_is_named():
    scenario = content.get_scenario("ship_without_crew")
    clocks = [{"id": "anchor", "location_id": "ship", "filled": 2, "segments": 4}]
    base = dict(scenario=scenario, visited_zones={"pier"}, clocks=clocks)
    hidden = map_state.build_table_map(**base, active_locations={"ship"}, task_levels={"hold_ship": 0})
    hint = map_state.build_table_map(**base, active_locations={"ship"}, task_levels={"hold_ship": 1})
    named = map_state.build_table_map(**base, active_locations={"ship"}, task_levels={"hold_ship": 2})
    dormant = map_state.build_table_map(**base, active_locations=set(), task_levels={"hold_ship": 2})
    assert hidden["clocks"] == []                                   # о ней ничего не знают
    assert dormant["clocks"] == []                                  # локацию ещё не посещали
    assert hint["clocks"][0]["name"] is None and hint["clocks"][0]["filled"] is None
    assert hint["clocks"][0]["stage"] == "uneasy"
    assert named["clocks"][0]["name"] == "Якорь" and (named["clocks"][0]["filled"], named["clocks"][0]["segments"]) == (2, 4)


def test_map_is_driven_by_scenario_data_not_hardcoded():
    scenario = copy.deepcopy(content.get_scenario("ship_without_crew"))
    scenario["zone_names"]["pier"] = "Причал-тест"
    m = map_state.build_table_map(scenario, {"pier"}, [], set(), {})
    assert {z["id"]: z["name"] for z in m["zones"]}["pier"] == "Причал-тест"
    scenario["adjacency"] = {"a": ["b"], "b": ["a", "c"], "c": ["b"]}
    scenario["zone_names"] = {"a": "А", "b": "Б", "c": "В"}
    scenario["layout"] = {}
    m = map_state.build_table_map(scenario, {"a"}, [], set(), {})
    assert {z["id"] for z in m["zones"]} == {"a", "b"}              # «в» за горизонтом, не раскрывается
