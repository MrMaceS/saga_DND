from fastapi import APIRouter

from app.engine import content

router = APIRouter(prefix="/api", tags=["stories"])


@router.get("/stories")
async def list_stories():
    """Каталог историй. «playable» = для неё есть валидный сценарий (остальные пока только наброски)."""
    return content.stories_catalog()
