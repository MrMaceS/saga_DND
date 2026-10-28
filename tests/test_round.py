"""Сценарные тесты раунда. Идентификаторы S-xx из docs/TEST_PLAN.md."""
import pytest
from app.engine.round import RoundState, RoundPhase, RoundManager, ActionDraft
from app.domain.errors import SagaError


def test_S_01_round_does_not_start_until_all_ready():
    """S-01: Раунд не переходит в resolving, пока не все готовы."""
    rs = RoundState(round_no=1, turn_status={"a": "turn_ended", "b": "thinking"})
    assert not rs.is_all_ready()
    with pytest.raises(RuntimeError):
        rs.transition_to_resolving()


def test_S_01_end_turn_can_be_undone():
    """S-01: «Закончить ход» можно отжать до последнего."""
    rs = RoundState(round_no=1, turn_status={"a": "thinking", "b": "thinking"})
    rs.end_turn("a")
    assert rs.turn_status["a"] == "turn_ended"
    rs.unend_turn("a")
    assert rs.turn_status["a"] == "thinking"
    assert not rs.is_all_ready()


def test_S_01_all_ready_transitions_to_resolving():
    rs = RoundState(round_no=1, turn_status={"a": "turn_ended", "b": "turn_ended"})
    assert rs.is_all_ready()
    rs.transition_to_resolving()
    assert rs.phase == RoundPhase.RESOLVING


def test_S_04_save_forbidden_in_resolving_and_narrating():
    """S-04: Сохранение запрещено в resolving и narrating."""
    rs = RoundState(round_no=1, turn_status={"a": "turn_ended"})
    assert rs.can_save()  # declaring
    rs.transition_to_resolving()
    assert not rs.can_save()
    rs.transition_to_narrating()
    assert not rs.can_save()
    rs.transition_to_saved()
    assert rs.can_save()


def test_S_05_phase_order_is_enforced():
    """S-05: Порядок фаз строго соблюдаются."""
    rs = RoundState(round_no=1, turn_status={"a": "turn_ended"})
    with pytest.raises(RuntimeError):
        rs.transition_to_narrating()  # нельзя из declaring
    rs.transition_to_resolving()
    with pytest.raises(RuntimeError):
        rs.transition_to_resolving()  # нельзя повторно
    rs.transition_to_narrating()
    with pytest.raises(RuntimeError):
        rs.transition_to_resolving()  # назад нельзя
    rs.transition_to_saved()


def test_S_06_actions_only_in_declaring():
    """S-06: Подача действий возможна только в declaring."""
    rs = RoundState(round_no=1, turn_status={"a": "thinking"})
    rs.submit_action("a", ActionDraft(hero_id="a", raw_text="test"))
    rs.end_turn("a")
    rs.transition_to_resolving()
    with pytest.raises(RuntimeError):
        rs.submit_action("a", ActionDraft(hero_id="a", raw_text="late"))


def test_S_07_round_manager_sequential():
    """Менеджер раундов ведёт последовательность."""
    rm = RoundManager()
    r1 = rm.start_round({"a": "turn_ended"})
    assert r1.round_no == 1
    r1.end_turn("a")
    r1.transition_to_resolving()
    r1.transition_to_narrating()
    r1.transition_to_saved()
    finished = rm.finish_round()
    assert finished.round_no == 1

    r2 = rm.start_round({"a": "turn_ended"})
    assert r2.round_no == 2


def test_auto_ready_statuses_count_as_ready():
    """Downed/unconscious/ai/away считаются готовыми автоматически."""
    rs = RoundState(round_no=1, turn_status={
        "a": "turn_ended",
        "b": "downed",
        "c": "ai",
        "d": "away",
    })
    assert rs.is_all_ready()