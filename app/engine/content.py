"""Каталоги контента: герои, истории, сценарии, кат-сцены (кеш в памяти, данные из data/)."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.engine.scene import ScenarioLoader, ScenarioValidationError

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
_loader = ScenarioLoader(DATA_DIR / "scenarios")


@lru_cache(maxsize=1)
def heroes_catalog() -> dict[str, dict[str, Any]]:
    data = json.loads((DATA_DIR / "heroes.json").read_text(encoding="utf-8"))
    return {h["id"]: h for h in data["heroes"]}


@lru_cache(maxsize=1)
def stories_catalog() -> list[dict[str, Any]]:
    stories = json.loads((DATA_DIR / "stories.json").read_text(encoding="utf-8"))
    for s in stories:
        # «Играбельна» только история, для которой есть валидный сценарий.
        s["playable"] = bool(s.get("playable")) and (DATA_DIR / "scenarios" / f"{s['id']}.yaml").exists()
    return stories


def story_by_id(story_id: str) -> dict[str, Any] | None:
    return next((s for s in stories_catalog() if s["id"] == story_id), None)


@lru_cache(maxsize=8)
def get_scenario(story_id: str) -> dict[str, Any]:
    """Загружает и валидирует сценарий. Бросает FileNotFoundError / ScenarioValidationError."""
    return _loader.load(story_id).data


@lru_cache(maxsize=1)
def cutscenes_catalog() -> dict[str, dict[str, Any]]:
    return json.loads((DATA_DIR / "cutscenes.json").read_text(encoding="utf-8"))


def cutscene_payload(cutscene_id: str) -> dict[str, Any] | None:
    cs = cutscenes_catalog().get(cutscene_id)
    if not cs:
        return None
    out = dict(cs)
    base = Path(cs["audio"]).with_suffix("")
    out["audio_url"] = next((f"/assets/{base}{ext}" for ext in (".mp3", ".ogg", ".wav") if (ASSETS_DIR / f"{base}{ext}").exists()), None)
    still = f"cutscenes/stills/{cs['id']}.webp"
    video = f"cutscenes/video/{cs['id']}.mp4"
    out["still_url"] = f"/assets/{still}" if (ASSETS_DIR / still).exists() else None   # без файлов остаются субтитры
    out["video_url"] = f"/assets/{video}" if (ASSETS_DIR / video).exists() else None
    return out


def zone_to_location(scenario: dict[str, Any]) -> dict[str, str]:
    return {z: loc_id for loc_id, loc in scenario["locations"].items() for z in loc["zones"]}


def hero_first_name(hero: dict[str, Any]) -> str:
    return hero["name"].split()[0]
