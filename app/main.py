import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import assets, cutscenes, dev, heroes, maps, saves, sessions, state, stories
from app.config import settings
from app.db.engine import engine, get_session, init_db
from app.db.repositories import SessionRepository
from app.domain.errors import SagaError
from app.ws import hand, table

logging.basicConfig(level=logging.INFO)
ROOT = Path(__file__).resolve().parent.parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if not settings.ai_enabled:
        logging.getLogger(__name__).warning("GEMINI_API_KEY не задан: работает офлайн-интерпретатор и шаблонный диктор")
    yield
    await engine.dispose()  # корректно закрываем соединения с БД при остановке


app = FastAPI(title="Сага Мьёльнира", version="0.2.0", lifespan=lifespan)


@app.exception_handler(SagaError)
async def saga_error_handler(request: Request, exc: SagaError):
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.detail}})


for r in (stories.router, heroes.router, sessions.router, maps.router, state.router, cutscenes.router,
          saves.router, assets.router, dev.router, table.router, hand.router):
    app.include_router(r)

web_dir = ROOT / "web"
assets_dir = ROOT / "assets"
assets_dir.mkdir(exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
if web_dir.exists():
    app.mount("/web", StaticFiles(directory=str(web_dir), html=True), name="web")


@app.get("/")
async def root():
    return RedirectResponse("/web/")


@app.get("/health")
async def health(session: AsyncSession = Depends(get_session)):
    db_ok = await SessionRepository(session).health_check()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok, "ai": settings.ai_enabled}
