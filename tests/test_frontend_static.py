"""Фронтенд не должен возвращаться к заглушкам: данные только с сервера, кубики только серверные."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parent.parent / "web"
JS = [p for p in WEB.rglob("*.js")]
HTML = [p for p in WEB.rglob("*.html")]


def test_pages_are_served(client):
    for path in ("/web/", "/web/table/", "/web/hand/", "/web/shared/styles.css", "/web/shared/map.js", "/web/table/table.js",
                 "/web/hand/hand.js"):
        assert client.get(path).status_code == 200, path
    assert client.get("/", follow_redirects=False).status_code in (302, 307)
    assert client.get("/assets/heroes/.gitkeep").status_code == 200


def test_no_client_side_dice_or_random_game_state():
    for f in JS:
        assert "Math.random" not in f.read_text(encoding="utf-8"), f"{f.name}: кубики и состояние бросает только сервер"


def test_no_hardcoded_hero_or_story_data_in_frontend():
    for f in JS + HTML:
        src = f.read_text(encoding="utf-8")
        assert not re.search(r"const\s+HEROES\s*=", src), f.name
        assert "Сигрид" not in src and "Эйрик Молот" not in src, f"{f.name}: имена героев приходят из /api/heroes"
        assert "Корабль без команды" not in src and "Тьёдвар" not in src, f"{f.name}: истории и тайны приходят с сервера"


def test_pages_talk_to_the_backend():
    table = (WEB / "table" / "table.js").read_text(encoding="utf-8")
    hand = (WEB / "hand" / "hand.js").read_text(encoding="utf-8")
    shared = (WEB / "shared" / "api.js").read_text(encoding="utf-8")
    assert "/api/stories" in shared and "/api/heroes" in shared and "/api/maps/" in shared
    assert "/ws/table/" in table and "/ws/hand/" in hand and "renderMap" in table and "renderMap" in hand
    assert "X-Table-Token" in table and "device_token" in hand


def test_zone_names_are_never_hardcoded_in_the_map_renderer():
    src = (WEB / "shared" / "map.js").read_text(encoding="utf-8")
    for word in ("трюм", "Трюм", "палуб", "Палуб", "каюта", "Каюта", "мачта", "Мачта"):
        assert word not in src, f"map.js не должен знать название зоны «{word}»"


def test_no_mock_markers_left_anywhere():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    markers = ("TODO", "FIXME", "заглушк", "stub", "mock_", "в реальном коде", "to_http_exception")
    for f in list(app_dir.rglob("*.py")) + JS + HTML:
        src = f.read_text(encoding="utf-8")
        for m in markers:
            assert m.lower() not in src.lower(), f"{f}: найден маркер заглушки «{m}»"


@pytest.mark.skipif(not shutil.which("node") or not (Path(__file__).parent / "e2e" / "node_modules" / "jsdom").exists(),
                    reason="нужен node и `npm install` в tests/e2e")
def test_browser_scenario_end_to_end():
    """Стол и два телефона проходят вечер до второго раунда (jsdom против живого сервера)."""
    run = subprocess.run(["bash", str(Path(__file__).parent / "e2e" / "run.sh")], capture_output=True, text=True, timeout=180)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-1500:]
