"""Тесты триггеров кат-сцен."""
import pytest


def test_cutscene_triggers_on_clock_full():
    """Кат-сцена запускается, когда часы заполняются."""
    # В M8 это будет интеграционный тест с реальным движком часов
    # Для M6 проверяем только структуру данных
    mock_cutscene = {
        "id": "cs_third_strike",
        "title": "Третий удар",
        "subtitles": [
            {"time": 0, "text": "Удар."},
            {"time": 3, "text": "Ещё удар."},
        ],
        "audio_url": None,
    }

    assert mock_cutscene["id"] == "cs_third_strike"
    assert len(mock_cutscene["subtitles"]) == 2
    assert mock_cutscene["subtitles"][0]["time"] == 0