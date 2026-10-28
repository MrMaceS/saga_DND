"""Лобби: создание, подключение, выбор героя, готовность, клятва, старт. Идентификаторы S-xx, H-xx из TEST_PLAN."""
import pytest

from helpers import Game


def test_stories_catalog_marks_only_real_scenarios_playable(client):
    stories = client.get("/api/stories").json()
    assert len(stories) == 5
    assert [s["id"] for s in stories if s["playable"]] == ["ship_without_crew"]
    assert all(s["allowed"] == [2, 10] for s in stories)


def test_heroes_catalog_has_eleven_without_secrets(client):
    heroes = client.get("/api/heroes").json()
    assert len(heroes) == 11
    assert {h["id"] for h in heroes} == {"ragnar", "astrid", "eirik", "sigrid", "vald", "gunnhild", "torvald",
                                         "bjorn", "leif", "helga", "halldora"}
    for h in heroes:
        assert sum(h["stats"].values()) == 9
        assert "secrets" not in h and "growth" not in h
    assert next(h for h in heroes if h["id"] == "eirik")["title"] == "Кузнец"


@pytest.mark.parametrize("body,code", [
    ({"name": "ab", "story_id": "ship_without_crew", "player_count": 4}, 422),
    ({"name": "Нормальная сага", "story_id": "ship_without_crew", "player_count": 1}, 422),
    ({"name": "Нормальная сага", "story_id": "ship_without_crew", "player_count": 11}, 422),
    ({"name": "Нормальная сага", "story_id": "nope", "player_count": 4}, 400),
    ({"name": "Нормальная сага", "story_id": "long_night", "player_count": 4}, 400),   # сценария ещё нет
])
def test_create_session_validation(client, body, code):
    assert client.post("/api/sessions", json=body).status_code == code


def test_create_returns_eight_symbol_code_and_unique_tokens(client):
    a = client.post("/api/sessions", json={"name": "Сага один", "story_id": "ship_without_crew", "player_count": 3}).json()
    b = client.post("/api/sessions", json={"name": "Сага два", "story_id": "ship_without_crew", "player_count": 3}).json()
    assert len(a["join_code"]) == 8 and a["join_code"] != b["join_code"]
    assert a["table_token"] != b["table_token"]


def test_session_full_and_join_validation(client):
    code = client.post("/api/sessions", json={"name": "Малая сага", "story_id": "ship_without_crew", "player_count": 2}).json()["join_code"]
    assert client.post(f"/api/sessions/{code}/join", json={"player_name": ""}).status_code == 422
    for n in ("a", "b"):
        assert client.post(f"/api/sessions/{code}/join", json={"player_name": n}).status_code == 200
    r = client.post(f"/api/sessions/{code}/join", json={"player_name": "c"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "session_full"
    assert client.post("/api/sessions/NOSUCHCD/join", json={"player_name": "x"}).status_code == 404


def test_hero_cannot_be_taken_twice_and_unknown_hero_is_rejected(client):
    code = client.post("/api/sessions", json={"name": "Спор героев", "story_id": "ship_without_crew", "player_count": 3}).json()["join_code"]
    t1 = client.post(f"/api/sessions/{code}/join", json={"player_name": "a"}).json()["device_token"]
    t2 = client.post(f"/api/sessions/{code}/join", json={"player_name": "b"}).json()["device_token"]
    assert client.post(f"/api/sessions/{code}/claim", json={"hero_id": "astrid", "device_token": t1}).status_code == 200
    r = client.post(f"/api/sessions/{code}/claim", json={"hero_id": "astrid", "device_token": t2})
    assert r.json()["error"]["code"] == "hero_taken"
    assert client.post(f"/api/sessions/{code}/claim", json={"hero_id": "NOPE", "device_token": t2}).json()["error"]["code"] == "unknown_hero"
    assert client.post(f"/api/sessions/{code}/claim", json={"hero_id": "eirik", "device_token": "bad"}).status_code == 401
    # смена героя до готовности освобождает прежнего
    assert client.post(f"/api/sessions/{code}/claim", json={"hero_id": "eirik", "device_token": t1}).status_code == 200
    assert client.post(f"/api/sessions/{code}/claim", json={"hero_id": "astrid", "device_token": t2}).status_code == 200


def test_ready_requires_hero(client):
    code = client.post("/api/sessions", json={"name": "Без героя", "story_id": "ship_without_crew", "player_count": 2}).json()["join_code"]
    t = client.post(f"/api/sessions/{code}/join", json={"player_name": "a"}).json()["device_token"]
    assert client.post(f"/api/sessions/{code}/ready", json={"device_token": t}).json()["error"]["code"] == "not_ready"
    assert client.post(f"/api/sessions/{code}/oath", json={"device_token": t}).json()["error"]["code"] == "not_ready"


def test_start_requires_table_token_everyone_ready_and_two_players(client):
    g = Game(client)
    url = f"/api/sessions/{g.code}/start"
    assert client.post(url).status_code == 401
    assert client.post(url, headers={"X-Table-Token": "bad"}).status_code == 401
    r = client.post(url, headers={"X-Table-Token": g.table_token})
    assert r.json()["error"]["code"] == "not_ready" and "Анна" in r.json()["error"]["message"]

    created = client.post("/api/sessions", json={"name": "Один в поле", "story_id": "ship_without_crew",
                                                 "player_count": 2}).json()
    tok = client.post(f"/api/sessions/{created['join_code']}/join", json={"player_name": "Один"}).json()["device_token"]
    client.post(f"/api/sessions/{created['join_code']}/claim", json={"hero_id": "astrid", "device_token": tok})
    client.post(f"/api/sessions/{created['join_code']}/oath", json={"device_token": tok})
    client.post(f"/api/sessions/{created['join_code']}/ready", json={"device_token": tok})
    r = client.post(f"/api/sessions/{created['join_code']}/start", headers={"X-Table-Token": created["table_token"]})
    assert r.json()["error"]["code"] == "not_ready" and "минимум 2" in r.json()["error"]["message"]


def test_start_twice_is_a_clean_error_not_a_500_and_lobby_closes(client):
    g = Game(client)
    assert g.start().status_code == 200
    again = client.post(f"/api/sessions/{g.code}/start", headers={"X-Table-Token": g.table_token})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_state"
    late = client.post(f"/api/sessions/{g.code}/join", json={"player_name": "Опоздавший"})
    assert late.json()["error"]["code"] == "lobby_closed"
    assert client.get(f"/api/sessions/{g.code}").json()["status"] == "playing"


def test_start_initializes_real_world_from_scenario(client):
    g = Game(client)
    g.start()
    st = g.hand_state("astrid")
    assert st["hero"]["cells_used"] == 0 and st["hero"]["wounds"] == []        # на старте все здоровы
    assert st["hero"]["inventory"] == ["топор", "факел"]
    assert st["hero"]["endurance"] == 5
    assert st["view"]["zone_id"] == "pier"
    assert {t["id"] for t in st["tasks"]} == {"check_hold", "hold_ship", "scout_shore"}
    assert all(t["level"] == 1 for t in st["tasks"])
    assert st["session"]["round_no"] == 1 and st["session"]["phase"] == "declaring"
    table = g.table_state()
    assert [p["hero_id"] for p in table["players"]] == ["astrid", "eirik"]
    assert table["tiles"][0]["name"] == "Корабль" and sorted(table["tiles"][0]["hero_ids"]) == ["astrid", "eirik"]
