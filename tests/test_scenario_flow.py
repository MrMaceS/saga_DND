"""Интеграционный тест полного цикла сцены. Идентификаторы M-xx."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_M_01_full_scenario_initialization_and_tick():
    """M-01: Сценарий инициализируется, часы тикают, кат-сцены триггерятся."""
    # 1. Создаём сессию и занимаем героя
    resp = client.post("/api/sessions", json={
        "name": "Full Scenario Test",
        "story_id": "ship_without_crew",
        "player_count": 2
    })
    code = resp.json()["join_code"]
    p1 = client.post(f"/api/sessions/{code}/join", json={"player_name": "P1"}).json()
    client.post(f"/api/sessions/{code}/claim", json={"hero_id": "astrid", "device_token": p1["device_token"]})

    # 2. Стартуем сцену
    start_resp = client.post(f"/api/sessions/{code}/start")
    assert start_resp.status_code == 200

    # 3. Проверяем, что сессия в статусе playing
    session_info = client.get(f"/api/sessions/{code}").json()
    assert session_info["status"] == "playing"
    assert session_info["round_no"] == 1

    # 4. Симулируем конец раунда (часы shore_shadows стартуют с 2, сегментов 6)
    # После 1-го тика: 3 (триггер cs_shadows_pier)
    # После 2-го тика: 4
    # После 3-го тика: 5
    # После 4-го тика: 6 (триггер cs_anchor_lost, если бы это были часы anchor, но тут shore_shadows)

    next_resp = client.post(f"/api/sessions/{code}/next_round")
    assert next_resp.status_code == 200
    assert "cs_shadows_pier" in next_resp.json()["triggered_cutscenes"]
    assert next_resp.json()["new_round"] == 2

    next_resp2 = client.post(f"/api/sessions/{code}/next_round")
    assert next_resp2.json()["new_round"] == 3