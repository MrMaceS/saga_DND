"""Контракт ИИ-слоя (A-01…A-08): схемы, проверка id, повторы, запасной режим, параметры вызова Gemini."""
import json

import pytest

from app.ai.client import AIClientError, GeminiClient, MockAIClient
from app.ai.fallback import narrator_fallback
from app.ai.interpreter import build_interpreter_context, interpret_action, validate_against_context
from app.ai.narrator import narrate
from app.ai.schemas import InterpreterResponse

CTX = build_interpreter_context(
    "astrid", ["pier", "deck", "rocks"], {"deck": ["палуба"], "rocks": ["берег"], "pier": ["пирс"]},
    [{"id": "scout_shore", "level": 1, "zone": "rocks", "phrases": {1: "Следить за тенями"}}],
    [], [], ["топор", "факел"], [], {"astrid": "pier", "eirik": "pier"},
    current_zone="pier", zone_names={"pier": "Пирс"})

VALID = {"hero_id": "astrid", "action_type": "investigate", "target_zone": "deck", "intent": "осмотреть палубу",
         "required_stat": "wits", "base": "normal", "requires_move_to": "deck"}


def run(coro):
    import asyncio
    return asyncio.run(coro)


def test_valid_answer_passes_and_hero_id_cannot_be_spoofed():
    client = MockAIClient([dict(VALID, hero_id="eirik")])
    out = run(interpret_action(client, "m", "astrid", "палуба", CTX))
    assert out["hero_id"] == "astrid" and out["target_zone"] == "deck"
    assert len(client.calls) == 1


def test_invalid_schema_triggers_retry_with_error_feedback():
    client = MockAIClient([{"action_type": "dance"}, VALID])
    out = run(interpret_action(client, "m", "astrid", "палуба", CTX))
    assert out["action_type"] == "investigate" and len(client.calls) == 2
    assert "Ошибка" in client.calls[1]["user_prompt"]


def test_unknown_zone_id_is_rejected_and_retried():
    bad = dict(VALID, target_zone="cabin", requires_move_to="cabin")
    client = MockAIClient([bad, VALID])
    out = run(interpret_action(client, "m", "astrid", "палуба", CTX))
    assert out["target_zone"] == "deck" and len(client.calls) == 2
    assert "cabin" in client.calls[1]["user_prompt"]


def test_unknown_hero_and_task_are_rejected():
    assert validate_against_context(dict(VALID, target_hero="nobody"), CTX)
    assert validate_against_context(dict(VALID, target_task="secret_task"), CTX)
    assert validate_against_context(dict(VALID, side_action={"type": "shout", "target_hero": "ghost", "content": "x"}), CTX)
    assert validate_against_context(VALID, CTX) == []


def test_three_failures_switch_to_the_offline_interpreter_with_a_real_answer():
    client = MockAIClient([{"x": 1}, {"x": 2}, {"x": 3}])
    out = run(interpret_action(client, "m", "astrid", "Осматриваю палубу", CTX))
    assert len(client.calls) == 3
    assert out["action_type"] == "investigate" and out["target_zone"] == "deck"      # не заглушка


def test_ai_outage_switches_to_the_offline_interpreter():
    client = MockAIClient([AIClientError("down")])
    out = run(interpret_action(client, "m", "astrid", "Жду", CTX))
    assert out["action_type"] == "wait" and not out["needs_clarification"]


def test_schema_has_no_numeric_difficulty_and_no_risk_field():
    fields = InterpreterResponse.model_fields
    assert "difficulty" not in fields and "risk" not in fields and "side_action" in fields


def test_narrator_uses_ai_text_and_falls_back_on_banned_words():
    good = MockAIClient([{"public": "Ветер несёт запах соли.", "private": {"astrid": "Ты слышишь стук."}}])
    out = run(narrate(good, "m", {"hero_profile": {"id": "astrid", "name": "Астрид"}, "outcome": "success"}))
    assert out["public"] == "Ветер несёт запах соли."
    bad = MockAIClient([{"public": "Бросок кубика удался.", "private": {}}] * 3)
    res = {"hero_profile": {"id": "astrid", "name": "Астрид Кровавая Луна"}, "outcome": "success",
           "revealed": ["В трюме кто-то есть"]}
    out = run(narrate(bad, "m", res))
    assert "кубик" not in out["public"].lower() and "бросок" not in out["public"].lower()
    assert "В трюме кто-то есть" in out["private"]["astrid"]


def test_fallback_narration_reveals_only_what_the_engine_revealed():
    out = narrator_fallback({"hero_profile": {"id": "astrid", "name": "Астрид Кровавая Луна"},
                             "outcome": "minimal_success", "revealed": ["В трюме кто-то есть"],
                             "clock_phrases": ["Канат натягивается сильнее"]})
    assert "Канат натягивается сильнее" in out["public"]
    assert out["private"] == {"astrid": "Астрид, ты узнаёшь: В трюме кто-то есть."}
    assert "Тьёдвар" not in json.dumps(out, ensure_ascii=False)


def test_gemini_client_passes_json_schema_via_response_json_schema(monkeypatch):
    """Регрессия: raw-схема с $defs раньше уходила в response_schema и ломала вызов."""
    captured = {}

    class FakeModels:
        def generate_content(self, model, contents, config):
            captured.update(model=model, config=config)
            return type("R", (), {"text": json.dumps({"ok": True}), "parsed": None})()

    class FakeClient:
        models = FakeModels()

    client = GeminiClient(api_key="k", timeout_s=5)
    client._client = FakeClient()
    schema = InterpreterResponse.model_json_schema()
    out = run(client.generate("gemini-2.5-flash", "sys", "user", 0.0, schema))
    assert out == {"ok": True}
    cfg = captured["config"]
    assert cfg.response_mime_type == "application/json" and cfg.response_json_schema == schema
    assert cfg.response_schema is None and captured["model"] == "gemini-2.5-flash"


def test_gemini_client_reports_failure_after_retries():
    class Boom:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise RuntimeError("503")

    client = GeminiClient(api_key="k", timeout_s=5, max_retries=2)
    client._client = Boom()
    with pytest.raises(AIClientError):
        run(client.generate("m", "s", "u", 0.0, {"type": "object"}))


def test_default_models_are_not_retired_ones():
    from app.config import Settings
    s = Settings(_env_file=None)
    assert "1.5" not in s.model_interpreter + s.model_narrator and "2.0" not in s.model_interpreter + s.model_narrator
