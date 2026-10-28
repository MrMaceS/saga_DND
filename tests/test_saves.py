"""Тесты сохранений. Идентификаторы P-xx соответствуют docs/TEST_PLAN.md."""
import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.db.engine import async_session
from sqlalchemy import text

client = TestClient(app)


def test_P_01_round_trip_save_and_load():
    """P-01: Круглый путь: создать, изменить состояние, сохранить, загрузить, проверить идентичность."""
    # 1. Создаём сессию и заходим
    resp = client.post("/api/sessions", json={"name": "Save Test", "story_id": "ship_without_crew", "player_count": 2})
    code = resp.json()["join_code"]

    p1 = client.post(f"/api/sessions/{code}/join", json={"player_name": "P1"}).json()
    client.post(f"/api/sessions/{code}/claim", json={"hero_id": "astrid", "device_token": p1["device_token"]})

    # 2. Эмулируем изменение состояния (через прямой SQL, так как API боя ещё в разработке)
    async def mutate_state():
        async with async_session() as session:
            res = await session.execute(text("SELECT id FROM game_session WHERE join_code = :code"), {"code": code})
            session_id = res.scalar()

            # Добавляем факт, известный только Астрид
            await session.execute(
                text(
                    "INSERT INTO fact (session_id, id, text, level, source, round_no) VALUES (:id, 'f1', 'Секрет', 1, 'own_action', 1)"),
                {"id": session_id}
            )
            await session.execute(
                text("INSERT INTO fact_known_by (session_id, fact_id, hero_id) VALUES (:id, 'f1', 'astrid')"),
                {"id": session_id}
            )
            # Добавляем ранение
            await session.execute(
                text(
                    "INSERT INTO injury (session_id, hero_id, body_part, side, severity, cells, round_no) VALUES (:id, 'astrid', 'arm', 'left', 'light', 1, 1)"),
                {"id": session_id}
            )
            # Меняем статус сессии
            await session.execute(
                text("UPDATE game_session SET round_no = 2, status = 'playing' WHERE join_code = :code"),
                {"code": code})
            await session.commit()

            # Запоминаем состояние ДО сохранения для сравнения
            res = await session.execute(text("SELECT round_no, status FROM game_session WHERE join_code = :code"),
                                        {"code": code})
            state_before = res.fetchone()

            res = await session.execute(text("SELECT COUNT(*) FROM injury WHERE session_id = :id"), {"id": session_id})
            injuries_before = res.scalar()

            res = await session.execute(text("SELECT COUNT(*) FROM fact WHERE session_id = :id"), {"id": session_id})
            facts_before = res.scalar()

            return session_id, state_before, injuries_before, facts_before

    session_id, state_before, injuries_before, facts_before = asyncio.run(mutate_state())

    # 3. Сохраняем
    save_resp = client.post(f"/api/saves/{code}?kind=manual&slot_no=1")
    assert save_resp.status_code == 200

    # Получаем ID сохранения
    list_resp = client.get(f"/api/saves/{code}")
    save_id = list_resp.json()[0]["id"]

    # 4. Эмулируем дальнейшее изменение состояния (которое должно быть перезаписано при загрузке)
    async def mutate_again():
        async with async_session() as session:
            await session.execute(
                text("UPDATE game_session SET round_no = 99, status = 'finished' WHERE join_code = :code"),
                {"code": code})
            await session.execute(text("DELETE FROM injury WHERE session_id = :id"), {"id": session_id})
            await session.execute(text("DELETE FROM fact WHERE session_id = :id"), {"id": session_id})
            await session.commit()

    asyncio.run(mutate_again())

    # 5. Загружаем сохранение
    load_resp = client.post(f"/api/saves/{code}/load?save_id={save_id}")
    assert load_resp.status_code == 200

    # 6. Проверяем, что состояние вернулось к точке сохранения
    async def verify_state():
        async with async_session() as session:
            res = await session.execute(text("SELECT round_no, status FROM game_session WHERE join_code = :code"),
                                        {"code": code})
            state_after = res.fetchone()

            res = await session.execute(text("SELECT COUNT(*) FROM injury WHERE session_id = :id"), {"id": session_id})
            injuries_after = res.scalar()

            res = await session.execute(text("SELECT COUNT(*) FROM fact WHERE session_id = :id"), {"id": session_id})
            facts_after = res.scalar()

            return state_after, injuries_after, facts_after

    state_after, injuries_after, facts_after = asyncio.run(verify_state())

    assert state_after.round_no == state_before.round_no
    assert state_after.status == state_before.status
    assert injuries_after == injuries_before
    assert facts_after == facts_before


def test_P_07_export_and_import():
    """P-07: Экспорт и импорт файла."""
    resp = client.post("/api/sessions",
                       json={"name": "Export Test", "story_id": "ship_without_crew", "player_count": 2})
    code = resp.json()["join_code"]

    client.post(f"/api/sessions/{code}/join", json={"player_name": "P1"})
    client.post(f"/api/saves/{code}?kind=manual")

    list_resp = client.get(f"/api/saves/{code}")
    save_id = list_resp.json()[0]["id"]

    # Экспорт
    export_resp = client.post(f"/api/saves/{code}/export?save_id={save_id}")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert "filename" in export_data
    assert "data" in export_data
    assert export_data["data"]["save_version"] == 1

    # Испортим данные в сессии
    async def corrupt():
        async with async_session() as session:
            await session.execute(text("UPDATE game_session SET name = 'CORRUPTED' WHERE join_code = :code"),
                                  {"code": code})
            await session.commit()

    asyncio.run(corrupt())

    # Импорт
    import_resp = client.post(f"/api/saves/{code}/import", json={"data": export_data["data"]})
    assert import_resp.status_code == 200

    # Проверка
    async def verify():
        async with async_session() as session:
            res = await session.execute(text("SELECT name FROM game_session WHERE join_code = :code"), {"code": code})
            return res.scalar()

    assert asyncio.run(verify()) == "Export Test"