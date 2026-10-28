from fastapi import APIRouter

from app.engine import content

router = APIRouter(prefix="/api", tags=["heroes"])


@router.get("/heroes")
async def get_heroes():
    """Каталог 11 героев для выбора. Тайны и скрытые данные не отдаются."""
    return [{
        "id": h["id"], "name": h["name"], "title": h["title"], "archetype": h["archetype"],
        "stats": h["stats"], "endurance": h["endurance"], "gift": h["gift"], "weakness": h["weakness"],
        "action_ability": h["action_ability"], "minor_ability": h["minor_ability"],
        "goal": h["goal"]["text"], "start_items": h["start_items"],
        "avatar_url": f"/assets/heroes/{h['id']}.webp",
    } for h in content.heroes_catalog().values()]
