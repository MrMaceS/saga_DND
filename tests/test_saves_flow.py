"""Сохранения (P-01…P-07)."""
import json
import time

import pytest

from helpers import Game, collect_until, until_state


@pytest.fixture()
def game(client):
    g = Game(client)
    g.start()
    yield g
    g.close()


def H(g):
    return {"X-Table-Token": g.table_token}


def play_round(g):
    g.send("astrid", "turn.end"); g.send("eirik", "turn.end")
    collect_until(g.hands["astrid"], "round.started")


def test_autosave_exists_after_start_and_replaces_itself_each_round(game):
    saves = game.client.get(f"/api/saves/{game.code}", headers=H(game)).json()
    assert [s["kind"] for s in saves] == ["auto"] and saves[0]["round_no"] == 1
    game.connect("astrid"); game.connect("eirik")
    play_round(game)
    saves = game.client.get(f"/api/saves/{game.code}", headers=H(game)).json()
    assert [s["kind"] for s in saves] == ["auto"] and saves[0]["round_no"] == 2


def test_saves_need_the_table_token(game):
    assert game.client.get(f"/api/saves/{game.code}").status_code == 401
    assert game.client.get(f"/api/saves/{game.code}", headers={"X-Table-Token": "bad"}).status_code == 401
    assert game.client.post(f"/api/saves/{game.code}/manual").status_code == 401


def test_manual_slots_are_limited_to_three(game):
    for _ in range(3):
        assert game.client.post(f"/api/saves/{game.code}/manual", headers=H(game)).status_code == 200
    r = game.client.post(f"/api/saves/{game.code}/manual", headers=H(game))
    assert r.json()["error"]["code"] == "slots_full"
    kinds = [s["kind"] for s in game.client.get(f"/api/saves/{game.code}", headers=H(game)).json()]
    assert kinds.count("manual") == 3


def test_no_rollback_in_the_middle_of_the_game(game):
    slot = game.client.post(f"/api/saves/{game.code}/manual", headers=H(game)).json()["slot_id"]
    r = game.client.post(f"/api/saves/{game.code}/load", json={"slot_id": slot}, headers=H(game))
    assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_state"


def test_save_and_exit_requires_everyone_then_load_restores_exact_state(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    game.dice(18)
    card = game.say("astrid", "Осматриваю палубу")
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    play_round(game)                                                    # раунд 2, Астрид нашла улики
    before = game.hand_state("astrid")
    assert game.client.post(f"/api/sessions/{game.code}/exit", headers=H(game)).status_code == 200
    game.send("astrid", "exit.vote", agree=True)
    until_state(a, lambda s: s["session"]["status"] == "playing")      # один голос ничего не меняет
    assert game.client.get(f"/api/sessions/{game.code}").json()["status"] == "playing"
    game.send("eirik", "exit.vote", agree=True)
    for _ in range(40):
        if game.client.get(f"/api/sessions/{game.code}").json()["status"] == "paused":
            break
        time.sleep(0.05)
    assert game.client.get(f"/api/sessions/{game.code}").json()["status"] == "paused"

    manual = next(s for s in game.client.get(f"/api/saves/{game.code}", headers=H(game)).json() if s["kind"] == "manual")
    # портим состояние и загружаем сохранение
    from sqlalchemy import create_engine, text
    import os
    path = os.environ["DATABASE_URL"].replace("sqlite+aiosqlite:///", "")
    with create_engine(f"sqlite:///{path}").begin() as conn:
        conn.execute(text("UPDATE game_session SET round_no = 99 WHERE join_code = :c"), {"c": game.code})
        conn.execute(text("DELETE FROM fact_known_by WHERE hero_id = 'astrid'"))
    r = game.client.post(f"/api/saves/{game.code}/load", json={"slot_id": manual["id"]}, headers=H(game))
    assert r.status_code == 200
    after = game.hand_state("astrid")
    assert after["session"]["round_no"] == before["session"]["round_no"] == 2
    assert after["clues"] == before["clues"] and after["hero"]["inventory"] == before["hero"]["inventory"]
    assert after["facts"] == before["facts"] and after["tasks"] == before["tasks"]


def test_resume_gives_new_table_token_and_old_one_stops_working(game):
    game.client.post(f"/api/saves/{game.code}/manual", headers=H(game))
    listed = game.client.get("/api/sessions/resumable").json()
    assert any(s["code"] == game.code for s in listed)
    resumed = game.client.post(f"/api/sessions/{game.code}/resume").json()
    assert resumed["table_token"] != game.table_token
    assert game.client.get(f"/api/saves/{game.code}", headers=H(game)).status_code == 401
    assert game.client.get(f"/api/saves/{game.code}", headers={"X-Table-Token": resumed["table_token"]}).status_code == 200


def test_export_and_import_validate_save_version(game):
    slot = game.client.post(f"/api/saves/{game.code}/manual", headers=H(game)).json()["slot_id"]
    snap = game.client.get(f"/api/saves/{game.code}/export/{slot}", headers=H(game)).json()
    assert snap["save_version"] == 2 and "player_binding" in snap["tables"]
    bad = dict(snap, save_version=1)
    r = game.client.post(f"/api/saves/{game.code}/import", json=bad, headers=H(game))
    assert r.status_code == 400                         # во время игры импорт запрещён в любом случае
    assert game.client.get(f"/api/saves/{game.code}/export/9999", headers=H(game)).status_code == 404
