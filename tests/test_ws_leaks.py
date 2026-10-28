import pytest
from engine import rules
from app.ws.filters import build_hand_payload


def test_V_01_visible_facts_filters_correctly():
    """V-01: Герой видит только свои факты."""
    facts = [
        {"id": "f1", "text": "Секрет Астрид", "known_by": ["astrid"]},
        {"id": "f2", "text": "Общий факт", "known_by": ["astrid", "eirik"]},
        {"id": "f3", "text": "Секрет Сигрид", "known_by": ["sigrid"]},
    ]

    # Астрид видит f1 и f2
    astrid_facts = rules.visible_facts(facts, "astrid")
    assert len(astrid_facts) == 2
    assert all(f["id"] in ("f1", "f2") for f in astrid_facts)

    # Эйрик видит только f2
    eirik_facts = rules.visible_facts(facts, "eirik")
    assert len(eirik_facts) == 1
    assert eirik_facts[0]["id"] == "f2"

    # Вальд не видит ничего
    vald_facts = rules.visible_facts(facts, "vald")
    assert len(vald_facts) == 0


def test_V_01_build_hand_payload_excludes_unknown_facts():
    """V-01: build_hand_payload не включает факты, где героя нет в known_by."""
    full_state = {
        "facts": [
            {"id": "f1", "text": "Секрет Астрид", "known_by": ["astrid"]},
            {"id": "f2", "text": "Общий факт", "known_by": ["astrid", "eirik"]},
        ]
    }

    payload = build_hand_payload("eirik", full_state)

    assert payload["hero_id"] == "eirik"
    assert len(payload["facts"]) == 1
    assert payload["facts"][0]["id"] == "f2"
    assert "Секрет Астрид" not in [f["text"] for f in payload["facts"]]