from fastapi import APIRouter

from app.domain.errors import SagaError
from app.engine import content

router = APIRouter(prefix="/api", tags=["cutscenes"])


@router.get("/cutscenes")
async def list_cutscenes():
    return [{"id": c["id"], "title": c["title"]} for c in content.cutscenes_catalog().values()]


@router.get("/cutscenes/{cutscene_id}")
async def get_cutscene(cutscene_id: str):
    """Субтитры и ссылка на аудио (audio_url = null, пока файл озвучки не положен в assets/)."""
    payload = content.cutscene_payload(cutscene_id)
    if not payload:
        raise SagaError("not_found", "Кат-сцена не найдена")
    return payload
