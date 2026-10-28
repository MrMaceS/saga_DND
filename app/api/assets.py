from fastapi import APIRouter

from app.engine import content

router = APIRouter(prefix="/api", tags=["assets"])


@router.get("/assets/manifest")
async def manifest():
    """Что из ассетов реально лежит на диске. Остального фронтенд заменяет запасными значками."""
    root = content.ASSETS_DIR
    files = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.name != ".gitkeep") if root.exists() else []
    return {"files": files, "count": len(files)}
