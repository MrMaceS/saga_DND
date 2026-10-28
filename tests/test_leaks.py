"""Видимость и утечки (V-01…V-11). Клиент получает только то, что знает его герой."""
import json

import pytest

from helpers import Game, collect_until, until, until_state

SECRETS = ("Тьёдвар", "Утопленник", "Сигурд", "оковы Эйрика")


@pytest.fixture()
def game(client):
    g = Game(client)
    g.start()
    yield g
    g.close()


def test_no_secrets_in_any_message_during_a_round(game):
    a, e, t = game.connect("astrid"), game.connect("eirik"), game.connect_table()
    game.dice(15)
    card = game.say("astrid", "Осматриваю палубу")
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    game.send("astrid", "turn.end"); game.send("eirik", "turn.end")
    seen = {"astrid": collect_until(a, "round.started"), "eirik": collect_until(e, "round.started"),
            "table": collect_until(t, "round.started")}
    for who, msgs in seen.items():
        blob = json.dumps(msgs, ensure_ascii=False)
        for secret in SECRETS:
            assert secret not in blob, f"{who} получил «{secret}»"


def test_private_findings_never_reach_other_heroes_or_the_table(game):
    a, e, t = game.connect("astrid"), game.connect("eirik"), game.connect_table()
    game.dice(18)
    card = game.say("astrid", "Осматриваю палубу в поисках ценного")
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    game.send("astrid", "turn.end"); game.send("eirik", "turn.end")
    eirik_msgs = collect_until(e, "round.started")
    table_msgs = collect_until(t, "round.started")
    for msgs in (eirik_msgs, table_msgs):
        blob = json.dumps(msgs, ensure_ascii=False)
        assert "Не открывайте трюм" not in blob and "мешочек" not in blob
    assert "Не открывайте трюм" not in json.dumps(game.hand_state("eirik"), ensure_ascii=False)


def test_table_state_contains_no_personal_data(game):
    ts = game.table_state()
    blob = json.dumps(ts, ensure_ascii=False)
    for forbidden in ("inventory", "facts", "secrets", "device_token", "table_token", "clues"):
        assert forbidden not in blob


def test_token_gives_only_own_hero_state(game):
    a = game.hand_state("astrid")
    e = game.hand_state("eirik")
    assert a["me"]["hero_id"] == "astrid" and e["me"]["hero_id"] == "eirik"
    assert "device_token" not in json.dumps(a) and "table_token" not in json.dumps(a)
    # чужой токен и токен Стола не открывают руку
    assert game.client.get(f"/api/hand/{game.code}", params={"device_token": game.table_token}).status_code == 401
    assert game.client.get(f"/api/table/{game.code}", headers={"X-Table-Token": game.tokens["astrid"]}).status_code == 401


def test_hero_id_in_messages_cannot_be_spoofed(game):
    a = game.connect("astrid")
    game.send("astrid", "turn.end", hero_id="eirik")      # лишнее поле игнорируется: герой берётся из токена
    until_state(a, lambda s: s["me"]["turn_status"] == "turn_ended")
    assert game.hand_state("eirik")["me"]["turn_status"] == "idle"


def test_heard_by_lists_only_heroes_in_the_same_zone(game):
    a = game.connect("astrid")
    assert [h["hero_id"] for h in game.hand_state("astrid")["heard_by"]] == ["eirik"]
    game.send("astrid", "move.step", target_zone="deck")
    st = until_state(a, lambda s: s["view"]["zone_id"] == "deck")
    assert st["heard_by"] == []


def test_hint_chips_are_built_from_known_things_only(game):
    st = game.hand_state("astrid")
    story = st["chips"]["story"]
    assert story and st["chips"]["simple"]
    for phrase in story:
        for forbidden in ("каюта", "мачта", "Тьёдвар"):
            assert forbidden.lower() not in phrase.lower()
    blob = json.dumps(st["map"], ensure_ascii=False)
    assert "cabin" not in blob and "mast" not in blob
