"""Показывает, каких картинок и озвучки ещё не хватает. Игра работает и без них (запасные значки и субтитры)."""
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
assets = ROOT / "assets"


def check(label: str, paths: list[str]) -> int:
    missing = [p for p in paths if not (assets / p).exists()]
    print(f"{label}: {len(paths) - len(missing)}/{len(paths)}")
    for p in missing:
        print(f"   нет: assets/{p}")
    return len(missing)


heroes = json.loads((ROOT / "data" / "heroes.json").read_text(encoding="utf-8"))["heroes"]
scenario = yaml.safe_load((ROOT / "data" / "scenarios" / "ship_without_crew.yaml").read_text(encoding="utf-8"))
cutscenes = json.loads((ROOT / "data" / "cutscenes.json").read_text(encoding="utf-8"))
total = 0
total += check("Портреты героев (768x1024, webp)", [f"heroes/{h['id']}.webp" for h in heroes])
views = [f"{v}.webp" for levels in scenario["views"].values() for v in levels.values()]
total += check("Виды мест (1280x720, webp)", sorted(set(views)))
total += check("Озвучка кат-сцен (mp3)", [c["audio"] for c in cutscenes.values()])  # допускаются также .ogg и .wav
total += check("Кадры кат-сцен (1280x720, webp, по желанию)", [f"cutscenes/stills/{c}.webp" for c in cutscenes])
print("\nВсё на месте." if not total else f"\nНе хватает файлов: {total}. Игра запустится и без них.")
