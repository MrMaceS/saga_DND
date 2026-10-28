"""Игровой поток по WebSocket: раунды, кубики сервера, часы, знания, согласия. S-01…S-14, R-xx, V-xx."""
import json
import time

import pytest
from starlette.websockets import WebSocketDisconnect

from app.ai import service
from app.ai.client import MockAIClient
from app.ws.hub import hub
from helpers import Game, collect_until, until, until_state, until_text, wait_disconnected


@pytest.fixture()
def game(client):
    g = Game(client)
    g.start()
    yield g
    g.close()


def end_round(g, *heroes):
    for h in heroes:
        g.send(h, "turn.end")


def finish_round(g, watcher="astrid"):
    return collect_until(g.hands[watcher], "round.started")


def test_ws_rejects_bad_tokens(client):
    g = Game(client)
    g.start()
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/hand/{g.code}?token=bad"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/table/{g.code}?token=bad"):
            pass
    with pytest.raises(WebSocketDisconnect):          # токен Стола не годится для руки и наоборот
        with client.websocket_connect(f"/ws/hand/{g.code}?token={g.table_token}"):
            pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/table/{g.code}?token={g.tokens['astrid']}"):
            pass


def test_connect_pushes_own_state_and_table_state(game):
    a = game.connect("astrid")
    t = game.connect_table()
    st = until(a, "hero.state")["payload"]
    assert st["me"]["hero_id"] == "astrid" and st["hero"]["name"].startswith("Астрид")
    ts = until(t, "table.state")["payload"]
    assert ts["session"]["status"] == "playing" and "facts" not in json.dumps(ts)


def test_round_waits_for_everyone_and_end_turn_can_be_undone(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    until(a, "hero.state")
    game.send("astrid", "turn.end")
    st = until_state(a, lambda s: s["me"]["turn_status"] == "turn_ended")
    assert st["session"]["round_no"] == 1
    game.send("astrid", "turn.unend")
    assert until_state(a, lambda s: s["me"]["turn_status"] == "idle")["session"]["round_no"] == 1
    assert game.hand_state("astrid")["session"]["round_no"] == 1


def test_free_text_search_rolls_server_dice_and_reveals_knowledge(game):
    a, e, t = game.connect("astrid"), game.connect("eirik"), game.connect_table()
    game.dice(15)                                       # d20 = 15
    card = game.say("astrid", "Осматриваю палубу в поисках ценного")
    assert card["card"]["action_type"] == "investigate" and card["card"]["difficulty"] == 12
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    end_round(game, "astrid", "eirik")
    msgs = finish_round(game)
    roll = next(m for m in msgs if m["type"] == "roll.public")["payload"]
    assert (roll["natural"], roll["dc"], roll["outcome"]) == (15, 12, "success")   # 15+1 = 16 против 12
    st = game.hand_state("astrid")
    assert st["session"]["round_no"] == 2
    assert "мешочек с тремя серебряными монетами" in st["hero"]["inventory"]
    assert any("Не открывайте трюм" in c["text"] for c in st["clues"])
    assert st["view"]["zone_id"] == "deck" and st["view"]["zone_name"] == "Палуба"
    # Эйрик (на пирсе) ничего из этого не знает
    other = game.hand_state("eirik")
    assert other["clues"] == [] and len(other["hero"]["inventory"]) == 2
    assert json.dumps(other, ensure_ascii=False).find("Не открывайте трюм") == -1
    assert {z["id"]: z["name"] for z in game.hand_map("eirik")["zones"]}["deck"] is None
    assert {z["id"]: z["name"] for z in game.hand_map("astrid")["zones"]}["deck"] == "Палуба"


def test_failed_roll_gives_no_information(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    game.dice(2)                                         # 2+1 = 3 против 12: провал с последствием
    card = game.say("astrid", "Осматриваю палубу")
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    end_round(game, "astrid", "eirik")
    finish_round(game)
    st = game.hand_state("astrid")
    assert st["clues"] == [] and len(st["hero"]["inventory"]) == 2


def test_clocks_tick_each_round_and_trigger_cutscenes(game):
    a, e, t = game.connect("astrid"), game.connect("eirik"), game.connect_table()
    end_round(game, "astrid", "eirik")
    finish_round(game)                                    # раунд 1: тени достигают 3, трескается «третий удар» 2/3
    cs1 = [m for m in collect_until(t, "round.started") if m["type"] == "cutscene.play"]
    ids = {m["payload"]["id"] for m in cs1}
    assert "cs_shadows_pier" in ids
    sub = next(m for m in cs1 if m["payload"]["id"] == "cs_shadows_pier")["payload"]["subtitles"]
    assert sub and sub[0]["text"].startswith("Тени выходят")
    end_round(game, "astrid", "eirik")
    finish_round(game)
    ids2 = {m["payload"]["id"] for m in collect_until(t, "round.started") if m["type"] == "cutscene.play"}
    assert "cs_third_strike" in ids2                       # третий удар заполнился на втором раунде
    clocks = {c["id"]: c for c in game.table_map()["clocks"]}
    assert clocks["third_strike"]["stage"] == "near_doom" and clocks["third_strike"]["filled"] is None


def test_understanding_a_threat_stops_its_clock(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    game.dice(18)                                       # 18+1 = 19 против 12: успех, уровень 2
    card = game.say("astrid", "Проверю канат")
    assert card["card"]["action_type"] == "investigate"
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    end_round(game, "astrid", "eirik")
    finish_round(game)
    anchor = {c["id"]: c for c in game.table_map()["clocks"]}["anchor"]
    assert anchor["named"] is True and (anchor["filled"], anchor["segments"]) == (0, 4)   # разобрались, не тикает
    end_round(game, "astrid", "eirik")
    finish_round(game)
    assert {c["id"]: c for c in game.table_map()["clocks"]}["anchor"]["filled"] == 0


def test_whisper_only_in_same_zone_and_shout_needs_a_roll(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    until(a, "hero.state"); until(e, "hero.state")
    game.send("astrid", "whisper.send", target_hero="eirik", content="тише")
    assert until(e, "feed.message")["payload"]["kind"] == "whisper"
    game.send("astrid", "move.step", target_zone="deck")
    until_state(a, lambda s: s["view"]["zone_id"] == "deck")
    game.send("astrid", "whisper.send", target_hero="eirik", content="слышишь?")
    until_text(a, "не долетит")
    game.dice(10)                                        # 10 + Дух 2 = 12 против 8 + 2 + 2 (ночь) = 12
    game.send("astrid", "shout.send", target_hero="eirik", content="Эйрик, сюда!")
    roll = until(a, "roll.public")["payload"]
    assert roll["dc"] == 12 and roll["outcome"] == "minimal_success"
    assert until(e, "feed.message")["payload"]["kind"] == "shout"
    game.send("astrid", "shout.send", target_hero="eirik", content="ещё раз")
    until_text(a, "один раз за раунд")


def test_joint_action_needs_consent_and_shares_one_roll(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    card = game.say("astrid", "Зову Эйрика осмотреть палубу")
    assert [c["hero_id"] for c in card["card"]["consent_from"]] == ["eirik"]
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    req = until_state(e, lambda s: s["consent_requests"])["consent_requests"]
    assert len(req) == 1 and req[0]["from_hero"] == "astrid"
    assert game.hand_state("astrid")["consent_requests"] == []        # просьба видна только адресату
    game.send("eirik", "consent.respond", action_id=req[0]["action_id"], accept=True)
    until_state(e, lambda s: s["me"]["turn_status"] == "in_group_action")
    game.dice(18)
    end_round(game, "astrid", "eirik")
    finish_round(game)
    assert any("Не открывайте трюм" in c["text"] for c in game.hand_state("eirik")["clues"])   # знание общее


def test_declined_consent_leaves_hero_alone(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    card = game.say("astrid", "Прошу Эйрика пойти со мной осмотреть палубу")
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    req = until_state(e, lambda s: s["consent_requests"])["consent_requests"]
    game.send("eirik", "consent.respond", action_id=req[0]["action_id"], accept=False)
    until_state(e, lambda s: not s["consent_requests"])
    game.dice(18)
    end_round(game, "astrid", "eirik")
    finish_round(game)
    assert game.hand_state("eirik")["clues"] == []


def test_disconnected_player_does_not_block_the_round(game):
    a, e = game.connect("astrid"), game.connect("eirik")
    until(a, "hero.state")
    e.close()
    wait_disconnected(game, "eirik")
    game.send("astrid", "turn.end")
    finish_round(game)
    assert game.hand_state("astrid")["session"]["round_no"] == 2


def test_unsupported_actions_are_rejected_honestly(game):
    a = game.connect("astrid")
    card = game.say("astrid", "Бью стража топором")
    assert card["card"]["is_possible"] is False and "не с кем драться" in card["card"]["rejection_reason"]
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    err = until(a, "error")["payload"]
    assert err["code"] == "action_unavailable"


def test_unclear_text_asks_a_question_and_cannot_be_confirmed(game):
    a = game.connect("astrid")
    card = game.say("astrid", "хм")
    assert card["card"]["needs_clarification"] is True and card["card"]["clarifying_question"]
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    assert until(a, "error")["payload"]["code"] == "action_unavailable"


def test_unknown_zone_names_do_not_exist_for_the_hero(game):
    a = game.connect("astrid")
    card = game.say("astrid", "Иду в каюту")
    assert card["card"]["needs_clarification"] is True              # каюты герой не знает: она не раскрывается


def test_move_step_rules(game):
    a = game.connect("astrid")
    game.send("astrid", "move.step", target_zone="hold")            # трюм не соседний с пирсом
    assert until(a, "error")["payload"]["code"] == "action_unavailable"
    game.send("astrid", "move.step", target_zone="rocks")           # берег: переход между локациями в конце раунда
    until_state(a, lambda s: s["moved_pending"] == "rocks")
    assert game.hand_state("astrid")["view"]["zone_id"] == "pier"   # пока ещё на пирсе


def test_ai_client_drives_interpretation_and_narration_when_available(game):
    ai = MockAIClient([
        {"hero_id": "astrid", "action_type": "investigate", "target_zone": "deck", "intent": "Осмотреть палубу",
         "required_stat": "wits", "base": "normal", "requires_move_to": "deck"},
        {"public": "Астрид ступает на мокрые доски.", "private": {"astrid": "Под шлюпкой что-то блеснуло."}},
    ])
    service.set_ai_client_for_tests(ai)
    a, e = game.connect("astrid"), game.connect("eirik")
    game.dice(15)
    card = game.say("astrid", "палуба")
    game.send("astrid", "action.confirm", action_id=card["action_id"])
    end_round(game, "astrid", "eirik")
    msgs = finish_round(game)
    public = [m["payload"]["text"] for m in msgs if m["type"] == "narration.public"]
    assert "Астрид ступает на мокрые доски." in public
    private = [m["payload"]["text"] for m in msgs if m["type"] == "feed.message"]
    assert "Под шлюпкой что-то блеснуло." in private


def test_settings_votes_follow_rules(game):
    # настройки меняются только в лобби
    other = Game(game.client)
    a, e = other.connect("astrid"), other.connect("eirik")
    other.send("astrid", "setting.propose", key="cruelty", value="bloody")
    vote = until_state(e, lambda s: s["votes"])["votes"][0]
    assert vote["rule"] == "unanimous" and other.hand_state("astrid")["session"]["settings"]["cruelty"] == "restrained"
    other.send("eirik", "setting.vote", vote_id=vote["id"], agree=True)
    until_state(a, lambda s: s["session"]["settings"]["cruelty"] == "bloody")
    other.close()
