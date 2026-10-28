# Ассеты

Игра подхватывает файлы по именам и сама заменяет отсутствующие запасными значками и субтитрами.
Проверить, чего не хватает: `python tools/check_assets.py`.

| Что | Куда | Формат |
|---|---|---|
| Портреты героев | `assets/heroes/{id}.webp` (id: ragnar, astrid, eirik, sigrid, vald, gunnhild, torvald, bjorn, leif, helga, halldora) | 768×1024 |
| Виды мест | `assets/views/{place}_{level}.webp` (имена в `data/scenarios/*.yaml`, раздел `views`) | 1280×720 |
| Кадры кат-сцен (фон под субтитрами) | `assets/cutscenes/stills/{cs_id}.webp` | 1280×720 |
| Видео кат-сцен (по желанию, без звука) | `assets/cutscenes/video/{cs_id}.mp4` | 16:9, до 8 с |
| Озвучка кат-сцен | `assets/audio/cutscenes/{cs_id}.mp3` (тексты в `data/cutscenes.json`) | mp3 |

Готовые промты для Gemini: `docs/gemini_asset_prompts.md` (озвучку делает `python tools/generate_voice.py`). Музыка и эмбиент пока не воспроизводятся игрой. Тексты для озвучки: `docs/offline_assets_plan.md`.
