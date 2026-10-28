# Промты для Gemini: герои, кат-сцены, озвучка, музыка

Промты на английском, потому что генераторы с ним работают точнее. Тексты озвучки на русском. Любые надписи на картинках модели искажают, поэтому в каждом промте стоит запрет на текст: имена и рамки рисует интерфейс.

## 0. Что чем делать (по документации Gemini API)

| Что | Инструмент Gemini | Заметка |
|---|---|---|
| Портреты, виды, кадры кат-сцен | генерация изображений Gemini (приложение Gemini или Google AI Studio) | формат кадра пишите в промте или выбирайте в интерфейсе |
| Видео для кат-сцен (по желанию) | Veo 3.1 | клип около 8 секунд, звук отключаем: голос диктора идёт отдельной дорожкой |
| Озвучка кат-сцен | Gemini 2.5 Flash TTS | скрипт `tools/generate_voice.py` сделает все 11 файлов; ключ нужен |
| Музыка и эмбиент | Lyria | инструментальные дорожки, швы петель сглаживайте в редакторе |
| Звуковые эффекты | отдельной модели нет | берите готовые CC0, список ниже |

Перед массовой генерацией проверьте в AI Studio актуальные названия моделей: линейка меняется. Игра подхватывает файлы по именам, чего-то одного достаточно, остальное заменится запасным вариантом.

### Как сохранить единый стиль
1. Сгенерируйте **Астрид** и принимайте её, пока стиль не понравится.
2. Для остальных героев прикладывайте Астрид и добавляйте строку: *«Use the attached image only as an art-style reference (line weight, palette, texture). Do not copy the character.»*
3. Одна картинка за запрос, без сеток и коллажей. Если модель рисует рамку или подпись, добавьте: *«Remove any frame, border, caption or text.»*
4. Сохраняйте в `webp`, портреты 768×1024, виды и кадры 1280×720 (например, через squoosh.app или `cwebp -q 85`).

## 1. Общий стиль (вставляйте в начало каждого промта вместо [STYLE])

```
STYLE: dark Norse woodcut and linocut illustration, hand-carved texture, bold black ink lines, limited palette of charcoal black, bone white, blood red accent and cold steel blue, subtle paper grain, moody and high contrast, flat graphic shapes, no photorealism, no 3D render, no text, no letters, no watermark, no frame
```

## 2. Герои (11). Файлы: `assets/heroes/{id}.webp`

Формат кадра 3:4, бюст, фон тёмный и простой, чтобы круглые токены обрезались чисто.

### Рагнар Соколиный Глаз, Ярл (`ragnar.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A young Viking jarl in his late twenties, broad shoulders, braided grey-gold beard, a signet ring on his hand, a hawk feather pinned to a fur-trimmed cloak, proud but tired eyes, a sword hilt at the shoulder. Accent color: steel blue cloak. No text, no frame, no modern items.
```

### Астрид Кровавая Луна, Берсерк (`astrid.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A fierce Viking berserker woman, red war-paint streaks across her face, wild dark braided hair, a bearskin over her shoulders, a battle axe resting on her shoulder, wide dangerous eyes. Accent color: blood red. No text, no frame, no modern items.
```

### Эйрик Молот, Кузнец (`eirik.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A heavy-set Viking blacksmith in his forties, soot-darkened forearms with old burn scars, a leather apron, a heavy hammer in hand, short beard singed at the ends, calm patient face. Accent color: ember orange glow from below. No text, no frame, no modern items.
```

### Сигрид Тихая, Разведчица (`sigrid.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A slim Viking scout woman, face half in shadow under a raven-black hood, a coil of rope with an iron grappling hook on her shoulder, narrow watchful eyes, light leather armor. Accent color: deep teal shadow. No text, no frame, no modern items.
```

### Вальд Вороний Певец, Скальд (`vald.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A lean Viking skald in his thirties, holding a small lyre, a dark cloak embroidered with ravens, ink-stained fingers, a half smile that hides something. Accent color: dark violet. No text, no frame, no modern items.
```

### Гуннхильд Вёльва, Знахарка (`gunnhild.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. An elderly Norse volva healer, bundles of dried herbs at her belt, a staff carved with runes, bone charms around her neck, clouded wise eyes, long grey braids. Accent color: moss green. No text, no frame, no modern items.
```

### Торвальд Морской Волк, Мореплаватель (`torvald.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A weathered Viking sailor in his forties, salt-crusted beard, a boarding hook in his hand, a compass-rune pendant, squinting against the wind, a rope-and-oilskin coat. Accent color: sea blue. No text, no frame, no modern items.
```

### Бьорн Медвежья Лапа, Охотник (`bjorn.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A massive Viking hunter in bear fur, a longbow across his back, a scar across one cheek, a wolf-tooth necklace, quiet heavy gaze, snow on the fur. Accent color: pale frost white. No text, no frame, no modern items.
```

### Лейв Пепельный, Вор (`leif.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A sly young Viking thief with an ash-smudged face, a dark hooded cloak, lockpicks at his belt, a crooked grin, restless clever eyes. Accent color: ash grey with a hint of gold. No text, no frame, no modern items.
```

### Хельга Руна, Жрица Одина (`helga.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A one-eyed priestess of Odin, a rune-carved leather patch over one eye, rune stones in her open hand, a black raven on her shoulder, long white-streaked hair, solemn gaze. Accent color: silver and indigo. No text, no frame, no modern items.
```

### Халльдора Щитовая, Щитоносица (`halldora.webp`)

```
[STYLE]. Vertical 3:4 bust portrait, three-quarter view, centered, plain dark charcoal background with subtle paper grain. A tall Viking shield-maiden, a round wooden shield painted with mismatched colors held in front of her, a spear in the other hand, a scarred chin, steady unshakable gaze. Accent color: faded yellow shield. No text, no frame, no modern items.
```

## 3. Враги (для боя, пока в игре не нужны). Файлы: `assets/enemies/{id}.webp`

**fog_guard**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A hollow figure in a sodden hooded cloak, the hood filled with pale mist instead of a face, no footprints, fog curling around its feet. Menacing but not graphic, no blood, no gore, no text.
```

**tyodvar**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A gaunt drowned man, seaweed in his beard, rusted rune-carved shackles on his wrists, water dripping from his sleeves, silver eyes. Menacing but not graphic, no blood, no gore, no text.
```

**wolf**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A gaunt winter wolf with frost on its fur, ribs showing, yellow eyes, snarling. Menacing but not graphic, no blood, no gore, no text.
```

**torch_raider**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A lean raider with a soot-black painted face, a torch in one hand and an axe in the other, a fur cap, tattered mail. Menacing but not graphic, no blood, no gore, no text.
```

**white_alpha**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A huge white wolf with old rune scars along its flank, one clouded eye, a plume of breath mist. Menacing but not graphic, no blood, no gore, no text.
```

**cold_debtor**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A tall figure made of black ice, an antler crown, glowing blue empty eye sockets, frozen chains of names inside its body, a raven on its shoulder. Menacing but not graphic, no blood, no gore, no text.
```

**assassin**

```
[STYLE]. Vertical 3:4 full-figure portrait on a plain dark background. A cloaked figure with the lower face covered by cloth, a steel knife in a gloved hand, a house signet ring visible on one finger. Menacing but not graphic, no blood, no gore, no text.
```

## 4. Виды мест на телефоне (16:9). Файлы: `assets/views/{имя}.webp`

Показываются по уровню раскрытия: уровень 1 только намёк, уровень 3 вся правда. Не рисуйте в нижних уровнях того, что герой ещё не знает.

**pier_night.webp**

```
[STYLE]. Horizontal 16:9 first-person view. A rotten wooden pier at night, a longship moored at its end, a frayed mooring rope, thick fog, black ravens on the posts, a pale moon behind clouds. No people unless stated, no text.
```

**deck_night.webp**

```
[STYLE]. Horizontal 16:9 first-person view. The wet deck of an abandoned Viking longship at night, an overturned small boat, coiled ropes, the mast rising into fog, dim moonlight, nobody on board. No people unless stated, no text.
```

**hold_1.webp**

```
[STYLE]. Horizontal 16:9 first-person view. The pitch-black open hatch of a ship's hold seen from above, only a faint glint of chain links in the dark, a thin curl of breath mist rising. No people unless stated, no text.
```

**hold_2.webp**

```
[STYLE]. Horizontal 16:9 first-person view. The inside of a longship's hold lit by a single torch, scattered barrels and crates, chains on the wet floor, a pale silhouette at the far end, water on the boards. No people unless stated, no text.
```

**hold_3.webp**

```
[STYLE]. Horizontal 16:9 first-person view. The same longship hold lit by torch, a gaunt drowned man kneeling in rune-carved chains, silver eyes, runes faintly glowing on the iron. No people unless stated, no text.
```

**rocks_1.webp**

```
[STYLE]. Horizontal 16:9 first-person view. Black rocks on a foggy shore at night, three hooded shapes barely visible in the mist. No people unless stated, no text.
```

**rocks_2.webp**

```
[STYLE]. Horizontal 16:9 first-person view. Three figures in sodden cloaks standing on wet sand between black rocks, no footprints behind them, thin fog. No people unless stated, no text.
```

## 5. Кат-сцены

### 5.1 Кадры (16:9). Файлы: `assets/cutscenes/stills/{id}.webp`

Кадр идёт фоном позади субтитров (затемнён), поэтому важны центр и тёмные края.

**cs_prologue** (Пролог)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A ruined fjord settlement under a thick unmoving fog, empty boats drifting, a lone longship on the horizon, a black raven on a broken roof beam. No text.
```

**cs_ship_arrives** (Корабль у пирса)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A whole but empty longship at a crooked pier at night, wet sails though no rain has fallen, thick fog, a faint knock implied by ripples on the water. No text.
```

**cs_shadows_pier** (Тени на пирсе)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. Straight-moving shadowy figures emerging from fog onto a wooden pier, they leave no footprints, cold steel-blue light. No text.
```

**cs_third_strike** (Третий удар)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A ship's hatch cracking like spring ice, cold vapor rising from the dark below, a hint of silver eyes in the blackness. No text.
```

**cs_hold_reveal** (Тот, кто в трюме)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A drowned man kneeling in rune-carved shackles in a torch-lit ship hold, water streaming from his sleeves, silver eyes looking up. No text.
```

**cs_anchor_lost** (Корабль уходит)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A longship slipping away into fog with a snapped mooring rope trailing in the water, empty pier behind it. No text.
```

**cs_defeat_guards** (Туман смыкается)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. Hooded misty figures dragging fallen warriors into fog along a shore, the shore fading, the camera low. No text.
```

**cs_end_free** (Оковы падают)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. Iron shackles falling onto wet planks, a hand rising from them, dawn-grey light, the sea calm and watching in the background. No text.
```

**cs_end_interrogate** (Ответы)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A dim cellar, a single torch, a bound man in shadow and a warrior's hands on a table, quiet tension, ink-like shadows. No text.
```

**cs_end_kill** (Вторая смерть)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. Runes flaring on iron chains in a dark hold and then going dark, water draining away, a cold blue mist left behind. No text.
```

**cs_end_leave** (Люк закрыт)

```
[STYLE]. Horizontal 16:9 cinematic still, dark vignette edges, calm center. A closed ship hatch at night, a heavy bar across it, faint scratching marks, fog curling around the planks. No text.
```

### 5.2 Видео Veo (по желанию). Файлы: `assets/cutscenes/video/{id}.mp4`

Если есть видео, Стол показывает его вместо кадра (без звука, зациклено). Загружайте кадр из 5.1 как первый кадр, если инструмент это позволяет.

**cs_prologue**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Slow drifting camera over fog-covered water toward a ruined fjord village, empty boats bobbing, a raven takes off from a roof. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_ship_arrives**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Static camera on a longship at a crooked pier, ripples, a deep wooden knock from below, fog rolling past. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_shadows_pier**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Slow push-in on the pier, straight shadowy figures step out of the fog one by one. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_third_strike**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Close shot of a ship hatch, wood cracking, cold vapor pouring out, silver glints in the dark. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_hold_reveal**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Slow push-in on a kneeling drowned man in rune-carved chains, water dripping, his silver eyes lift toward the camera. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_anchor_lost**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Side view, a rope snaps and the longship glides into fog while the pier stays empty. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_defeat_guards**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Low camera along the shore, hooded misty figures drag bodies into the fog, the shore dissolves. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_end_free**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Close on iron shackles dropping onto planks, then a pan up to a man breathing deeply in grey dawn light. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_end_interrogate**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Slow lateral move across a dim cellar table, torchlight flickering, shadows on a bound man. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_end_kill**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Runes on chains flare red then die out, water drains from the floor, blue mist lingers. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

**cs_end_leave**

```
Dark Norse woodcut-inspired animation, hand-carved texture, charcoal, bone white, blood red and steel blue palette, 16:9, 8 seconds. Static shot of a barred hatch, a faint scratching sound, fog curling across the planks. Slow, ominous, minimal motion. No speech, no dialogue, no text, no subtitles, no music, quiet ambient sound only.
```

## 6. Озвучка кат-сцен (Gemini TTS)

Файлы: `assets/audio/cutscenes/{id}.mp3` (подходят также `.ogg` и `.wav`). Голос один на все сцены.

### Быстрый путь: скрипт
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=ваш_ключ
python tools/generate_voice.py --voice Algenib --only cs_prologue cs_third_strike   # проба на двух
python tools/generate_voice.py --voice Algenib                                      # все 11
```
Сначала опробуйте 2–3 голоса (низкие мужские: `Algenib`, `Charon`, `Orus`) на одной фразе и выберите. Идентификатор TTS-модели при необходимости задайте `--model` (по умолчанию `gemini-2.5-flash-preview-tts`, проверьте в документации). Готовые mp3 нужны ffmpeg, без него останутся wav.

### Указание голосу (если озвучиваете вручную в AI Studio)

```
Read as a dark Norse saga narrator: a low, slow, slightly gravelly male voice, restrained and ominous, never theatrical. Pause briefly after each sentence. Speak in Russian:
```

### Тексты (вставлять после указания голосу)

**cs_prologue** (Пролог)

```
Давно, когда фьорд Хладмарк ещё был богат, над ним поднялся туман, который не рассеивался три зимы. Люди начали исчезать. Лодки возвращались пустыми. Вы последние, кто остался. И этой ночью море принесло к вашему пирсу корабль.
```

**cs_ship_arrives** (Корабль у пирса)

```
Ночь опустилась на Хладмарк. У покосившегося пирса стоит драккар, целый, но без единого живого на палубе. Его паруса мокры, хотя дождя не было. В трюме что-то ударяет в доски. Раз. Пауза. Ещё раз.
```

**cs_shadows_pier** (Тени на пирсе)

```
Тени выходят из тумана. Они двигаются слишком ровно и не оставляют следов. Они пришли за кораблём. Или за тем, кто в трюме.
```

**cs_third_strike** (Третий удар)

```
Третий удар. Люк трескается, как лёд весной. Из темноты поднимается холод, а вместе с ним голос, который знает ваши имена.
```

**cs_hold_reveal** (Тот, кто в трюме)

```
В оковах стоит на коленях человек, которого море не взяло и не отпустило. Вода стекает с его рукавов. Серебряные глаза поднимаются к вам. «Я Тьёдвар, слуга Сигурда, — говорит он. — Выпустите меня, и я скажу, кто сжёг Хладмарк».
```

**cs_anchor_lost** (Корабль уходит)

```
Канат лопается с глухим стоном. Драккар вздыхает, как зверь, которого спустили с привязи, и уходит в туман. Он вернётся. Но уже не пустым.
```

**cs_defeat_guards** (Туман смыкается)

```
Туман смыкается над вами. Вас уносят так же, как уносили тех, чьи лодки возвращались пустыми. Вы приходите в себя на палубе, а берег уже далеко.
```

**cs_end_free** (Оковы падают)

```
Оковы падают на доски. Тьёдвар вдыхает ночь, как человек, который слишком долго был под водой. «Я верен слову, пока не найден ярл», — шепчет он. Море за вашей спиной молчит. Пока.
```

**cs_end_interrogate** (Ответы)

```
Ответы падают в тишину, как камни в воду. Вы узнали многое. Правда ли это, решать вам, а не ему.
```

**cs_end_kill** (Вторая смерть)

```
Оковы вспыхивают рунами и смыкаются в последний раз. Тьёдвар умирает второй раз. Вода уходит из трюма, а холод остаётся и становится злее. Хладмарку это не простят.
```

**cs_end_leave** (Люк закрыт)

```
Люк закрыт. Ударов больше не слышно, но все знают, что внизу кто-то ждёт. Ждать он умеет дольше, чем вы.
```

Что проверить на слух: нет спешки, ударения в именах (Тьёдвар, Сигурд, Хладмарк) верные, нет театральности. Если голос слишком быстрый, добавьте в указание *«very slow pace, long pauses»*.

## 7. Музыка и эмбиент (Lyria). Файлы: `assets/audio/music/*.ogg`, `assets/audio/ambience/*.ogg`

Нужны инструментальные петли по 60–90 секунд без вокала. Склейте начало и конец кроссфейдом в любом аудиоредакторе. **Воспроизведение музыки и эмбиента в игре пока не подключено** (сейчас звучит только озвучка кат-сцен), файлы заготовьте заранее.

**music/calm_hladmark.ogg** (спокойная тема)

```
Instrumental dark folk, slow tempo, nyckelharpa and low frame drum, sparse and melancholic, cold Nordic mood, no vocals, no choir, gentle build, 75 seconds.
```

**music/threat_rise.ogg** (нарастание угрозы)

```
Instrumental dark ambient with low drones, slow tremolo strings and a distant heartbeat drum that slowly intensifies, uneasy and tense, no melody, no vocals, 75 seconds.
```

**music/battle_drums.ogg** (бой)

```
Instrumental Norse war drums and deep horns, driving rhythm, aggressive but controlled, tagelharpa drones, no vocals, 60 seconds.
```

**ambience/night_pier.ogg**

```
Ambient soundscape of a foggy fjord pier at night: slow water lapping, wet wood creaking, distant wind, an occasional raven call, no music, no melody, seamless texture, 60 seconds.
```

**ambience/longhouse_fire.ogg**

```
Ambient soundscape inside a wooden longhouse: a crackling fire, soft wind through timber, a distant wolf howl, no music, seamless texture, 60 seconds.
```

## 8. Звуковые эффекты (список для готовых CC0-библиотек)

Отдельной модели эффектов в Gemini API нет, поэтому берите готовые звуки с лицензией CC0 или аналогичной (проверьте условия на сайте источника) и называйте по списку. Файлы: `assets/audio/sfx/{имя}.ogg`.

| Имя | Что |
|---|---|
| `knock_hold_1`, `knock_hold_2`, `knock_hold_3` | глухой удар из-под палубы |
| `dice_roll`, `dice_land` | бросок и падение кубика |
| `anchor_scrape` | скрежет якоря по дну |
| `rope_snap` | лопнувший канат |
| `hatch_crack` | треск люка |
| `sword_clash`, `axe_hit`, `wound_hit` | бой |
| `wolf_howl`, `raven_caw` | животные |
| `torch_flare` | вспышка факела |
| `whisper` | шёпот |
| `horn` | рог |

## 9. Порядок работы
1. Портрет Астрид, стиль принят. 2. Остальные 10 героев по образцу. 3. Семь видов места. 4. Одна кат-сцена целиком: кадр, голос, (видео). 5. Остальные кат-сцены. 6. Музыка и эмбиент. После каждого шага запускайте `python tools/check_assets.py`.
