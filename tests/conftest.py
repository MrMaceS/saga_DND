import os
import sys
import tempfile
from pathlib import Path

# Окружение должно быть настроено ДО импорта приложения (движок БД создаётся при импорте).
_TMP = tempfile.mkdtemp(prefix="saga_tests_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP}/test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["DEV"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_globals():
    from app.ai import service
    from app.engine import dice_provider
    from app.services import votes
    from app.ws.hub import hub
    hub.reset()
    votes._memory.clear()
    dice_provider.set_roller(None)
    service.set_ai_client_for_tests(None)
    yield
    hub.reset()


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c
