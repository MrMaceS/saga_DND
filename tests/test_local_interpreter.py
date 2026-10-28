"""Офлайн-интерпретатор: те же ожидания, что и от Gemini (A-04, A-05, V-09)."""
import pytest

from app.ai.local_interpreter import interpret_local

CTX = {
    "hero_id": "astrid", "current_zone": "pier",
    "zones": ["pier", "deck", "rocks", "hold"],
    "zone_names": {"pier": "Пирс"},
    "zone_aliases": {"pier": ["пирс"], "deck": ["палуба"], "rocks": ["камни", "берег"], "hold": ["трюм", "люк"]},
    "tasks": [
        {"id": "check_hold", "level": 1, "zone": "hold", "phrases": {1: "Прислушаться к стуку", 2: "Спуститься в трюм"}},
        {"id": "scout_shore", "level": 1, "zone": "rocks", "phrases": {1: "Следить за тенями", 2: "Осмотреть берег"}},
    ],
    "items": ["топор", "факел"],
    "others_in_scene": [{"id": "eirik", "names": ["Эйрик"], "zone": "pier"}, {"id": "sigrid", "names": ["Сигрид"], "zone": "rocks"}],
}


def run(text):
    return interpret_local(text, CTX)


def test_search_zone():
    r = run("Осматриваю палубу в поисках ценного")
    assert (r["action_type"], r["target_zone"], r["requires_move_to"]) == ("investigate", "deck", "deck")
    assert r["required_stat"] == "wits" and not r["needs_clarification"]


def test_known_task_by_words():
    r = run("Прислушиваюсь к стуку")
    assert r["action_type"] == "investigate" and r["target_task"] == "check_hold"


def test_request_to_other_hero_needs_consent():
    r = run("Прошу Сигрид проверить берег")
    assert r["needs_consent_from"] == ["sigrid"] and r["target_zone"] == "rocks"


def test_whisper_and_shout_are_side_actions():
    w = run("Шепчу Эйрику, что в трюме кто-то есть")
    assert w["side_action"]["type"] == "whisper" and w["side_action"]["target_hero"] == "eirik"
    s = run("Кричу Эйрику, что в трюме кто-то есть")
    assert s["side_action"]["type"] == "shout" and s["needs_consent_from"] == []


def test_joint_action_keeps_main_action_and_side_shout():
    r = run("Беру факел и зову Эйрика осмотреть палубу")
    assert r["action_type"] == "investigate" and r["needs_consent_from"] == ["eirik"]
    assert r["side_action"]["type"] == "shout" and "prepared" in r["difficulty_tags"]


@pytest.mark.parametrize("text", ["Бью стража топором", "Атакую", "Стреляю из лука"])
def test_fighting_words_become_combat(text):
    assert run(text)["action_type"] == "combat"


@pytest.mark.parametrize("text", ["", "хм", "Я действую осторожно"])
def test_unclear_asks_question(text):
    r = run(text)
    assert r["needs_clarification"] and r["clarifying_question"] and "id" not in r["clarifying_question"]


def test_unknown_zone_is_not_recognized():
    assert run("Иду в каюту")["needs_clarification"]


def test_careful_and_hurried_tags():
    assert "careful" in run("Тихо осматриваю палубу")["difficulty_tags"]
    assert "rushed" in run("Быстро осматриваю палубу")["difficulty_tags"]


def test_wait():
    assert run("Жду")["action_type"] == "wait"
