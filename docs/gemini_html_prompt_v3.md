# Промт для Gemini: HTML-прототип v3

Как использовать: вставьте весь блок ниже в Gemini. Если он обрежет ответ, напишите: «Продолжи с того места, где остановился» или попросите по частям (строки в конце файла).

```
You are a senior game UI designer and front-end developer. Build ONE
self-contained HTML file (HTML + CSS + vanilla JS, Google Fonts allowed, no
other libraries) that is a clickable prototype of a local co-op Norse RPG
"Сага Мьёльнира". ALL UI text in Russian. Fake data, no backend. Add short
comments where WebSocket events would plug in.
Every map, portrait and silhouette MUST be actually drawn as inline SVG.
No placeholders, no "lorem", no empty boxes.

=== CONCEPT ===
2-10 players in ONE room on one Wi-Fi. An AI narrator is the game master,
TEXT ONLY (no synthetic voice). Sound = ambience and effects from the TABLE
only. TABLE = shared TV screen (16:9). HANDS = each player's phone (portrait).
The host is an ordinary player. Rounds, no timer: everyone presses
"Закончить ход" (can be un-pressed until the last player presses it).

=== STYLE ===
Dark Norse woodcut/linocut: charcoal, bone white, blood red accent, steel
blue for fog and water. Carved wood panels, rune frames, iron rivets, paper
grain, hand-inked lines. Large icons, high contrast, readable on a TV.

=== FIVE RULES THAT MUST BE VISIBLE IN THE UI ===
1. NO HINT LABELS ON MAPS. Zones on maps have no text names and no clickable
   hint buttons ("трюм", "палуба", "каюта" must NOT appear as labels). The
   player works out where things are. A zone gets a name only after some hero
   has entered it (demo: "Палуба" and "Пирс" are named because heroes stand
   there; hold, mast and cabin are unnamed fogged silhouettes with "?").
   The quick-action chips ("Проверить трюм", "Удержать корабль", ...) are
   REMOVED by default. Personal setting "Подсказки новичкам" (default OFF)
   brings generic chips back.
2. EVERYONE IS HEALTHY AT THE START. All Стойкость cells are empty, no wounds
   on any silhouette. Wounds appear ONLY after pressing demo buttons
   ("Демо: получить удар"). Demo wounds then show on the silhouette.
3. FREE TEXT EVERYWHERE: exploration, attack, defense, interrogation. Each
   free text is followed by a card "Я понял так" with the recognized
   interpretation and [Подтвердить] [Исправить]. No fixed attack buttons.
4. INTERROGATION RELIABILITY IS HIDDEN. The player never sees whether a
   prisoner told the truth. No "надёжность" meter or icon.
5. REPUTATION/ATTITUDE is shown only for NPCs toward the party in four
   steps: враждебное, настороженное, нейтральное (default), дружелюбное.
   There are NO relationship meters between players' heroes.

=== TOP SWITCHER (prototype navigation) ===
Стартовое меню (ТВ) | Стартовое меню (телефон) | Лобби (ТВ) | Лобби
(телефон) | Клятва | СТОЛ | РУКИ | Общая карта | Бой | Допрос | Настройки |
Сохранение

=== 1. START MENU ===
TV: title "Сага Мьёльнира", longship and fjord illustration, buttons «Новая
сага», «Продолжить сагу» (list of saves: name, chapter, round, date, hero
portraits, badge авто/вечер/ручное), «Герои» (11 cards), «Правила»,
«Настройки», «Экспорт / Импорт».
Phone: «Присоединиться по коду» (VIKING42), «Создать сагу», «Герои»,
«Правила», «Настройки».
Create saga form: session name, 5 story cards (Пепел Ярла, Корабль без
команды, Долгая Ночь, Клятва Ворона, Пир Предателей) each with genre and
recommended players; all playable for 2-10; player count 2-10 with the hint
«Сложность и число врагов не меняются».

=== 2. LOBBY ===
TV: code VIKING42, URL http://192.168.1.42:8000, players with hero portraits
and ready ticks, panel «Настройки вечера»:
 - «Чтец»: Выкл / По кругу / Добровольцы. Majority decides.
 - «Эмбиент и музыка»: on/off. Majority decides.
 - «Жестокость»: Сдержанная / Кровавая. Unanimous consent.
 A change shows a vote card on every phone: «Игрок X предлагает… [Согласен]
 [Против]».
Phone: carousel of 11 hero cards (locked ones show a chain and the player's
name), «Хочу читать вслух» (only when Reader = Добровольцы), «Готов».
Reader gets a badge "📖 Читает вслух" on the TV and on their phone. The
Reader reads ONLY public narrator text.

=== 3. OATH (start of EVERY evening) ===
Text: «Я говорю вслух только то, что услышал бы мой герой. Я не подсказываю
тем, кто далеко. Тайны моего героя остаются моими.» Each player holds a rune
button 3 seconds (progress ring). «Начать сагу» unlocks when all have sworn.

=== 4. TABLE SCREEN (main, with a BIG visible map) ===
Layout 16:9:
 - LEFT ~65%: FOCUS MAP, the biggest element. Plaque "Фокус: Корабль без
   команды". Fully drawn top-down cutaway of an abandoned longship at a pier
   at night, with planks, ribs, a hatch, a mast, a cabin roof, ropes, barrels.
   NO text labels on zones (see rule 1). Fog of war tied to info level:
   0 dark, 1 silhouette with "?", 2 creature and partial detail, 3 revealed.
   Hero tokens (round, portraits) stand on zones; 4+ heroes in a zone = one
   stacked token "×N". Fog edges are ink-wash.
 - TOP RIGHT: small overview of the settlement, 5 location nodes.
 - MIDDLE RIGHT: three threat clocks as segmented rune circles: «Якорь» 3/4,
   «Тени на берегу» 2/6, «Третий удар» 1/3.
 - BOTTOM ROW: at most 4 small location tiles (берег, длинный дом, кузница,
   док): mini portraits, nearest clock, "ход закончен" ticks.
 - VERY BOTTOM: narrator subtitle bar (text only).
 - TOP BAR: round number, "📖 Читает вслух: Вальд", buttons «Общая карта»,
   «Настройки», a floppy-disk icon (blinks after autosave; menu
   «Сохранить» / «Сохранить и выйти»; disabled during round resolution with
   the hint «Сохранение после раунда»).
 - Banner «Отряд разделён. Говорите только с теми, кто рядом» when heroes
   are in different places.
 - Max 5 occupied locations (1 focus + 4 tiles). A 6th shows a disabled
   button «Все 5 мест заняты. Сначала кто-то должен вернуться».
 - Player status chips: «думает» / «действие выбрано» / «ход закончен».
 - Demo buttons: "все закончили ход" -> narrator resolves locations one by
   one (camera moves between focus and tiles), clocks advance, dice roll.
 - Dice: server rolls, player presses a button, d20 animation, result scale:
   nat 1 crit fail; 5+ under DC fail with consequence; 1-4 under fail;
   0..+2 minimal success (hint only); +3..+7 success; +8 or nat 20 great.

=== 5. WORLD MAP (more detailed than before) ===
Hand-inked parchment map of the fjord settlement Хладмарк, TV-sized, with
zoom (+/-) and drag-to-pan on desktop. Draw: fjord water with wave lines,
cliffs, pine forest, black rocks, ice bay, footpaths, pier, longhouse, forge,
barn, watchtower, hilltop sanctuary, ship at the pier.
Only locations visited by at least one hero are drawn in ink with names;
undiscovered areas are blank paper edge (not greyed). Each location has:
 - status badge: active (red flame), empty (grey), unknown for long (faded
   "?"), mini hero tokens;
 - threat clock with «известно на раунд N» (clocks of empty places keep
   ticking, the map shows the last known value);
 - tap/click opens a location card: name, who is there, known tasks with
   info level (намёк / частичная правда / полная правда), known routes.
 - routes between locations as dashed ink lines; travelling groups show
   «в пути» with a small travel clock.
 - legend (flame, empty, unknown, travelling) and a compass rose.
Never show personal finds or secrets.

=== 6. PHONE ("Руки") ===
Header always visible: hero portrait, name, СТОЙКОСТЬ cells, Судьба ◆,
ability icons (lit = ready, dim = used this scene), turn-status chip, small
indicator «сохранено, раунд 7».
Bottom tabs: Локация | Рюкзак | Моя сага | Тело.

ЛОКАЦИЯ tab has a toggle «Зоны / Мир»:
 - «Зоны»: close-up drawn map of the hero's own zone with personal fog.
   Adjacent zones are shown as unlabeled tappable areas on the drawing;
   tapping one moves there (free step). A zone's name appears only after
   the hero has been there. No hint buttons.
 - «Мир»: PERSONAL WORLD MAP, the same drawing as the common map plus: a
   pulsing marker «Ты здесь», locations this hero visited marked with a
   footprint, locations known only from others marked with an ear/rumor
   icon, and the hero's own notes pinned to places (visible only to them).
   Pinch-zoom and drag.
 - below the map: ribbon «Тебя слышат: Астрид, Эйрик»; known tasks with
   info-level badges (only those the hero knows); free text «Что делает
   герой?»; after sending, the "Я понял так" card (type, target, stat,
   difficulty, [Подтвердить][Исправить]); buttons «Шепнуть» (same zone,
   free), «Окрикнуть» (Дух, base DC 8, +2 noise or night, +2 per zone of
   distance, once per round, does not use the main action), «Закончить
   ход». Joint-action proposal card: [Присоединиться][Отклонить]
   [Предложить другой план]. Reader block «Читай вслух» if the player is
   the Reader.

РЮКЗАК: 4 slots + 2 locked backpack slots; items: топор, факел, 2 empty.
Item card: [Использовать][Передать][Убрать в сундук] (chest disabled with
«Сундук только в длинном доме»). Separate shelf «Записки и улики» (no slots).

МОЯ САГА: goal with 3 steps; two secrets (one "Ты знаешь" with «Знает:
только ты», one "Запечатано" as a sealed envelope with «Что-то с тобой не
так»); knowledge journal (fact, level, source, [Поделиться] only for heroes
in the same zone); private narrator notes; «Мои записи»; weakness card.

ТЕЛО: hero silhouette (NO wounds at start). Demo buttons add wounds, shown
red with penalty labels ("Правая рука: средняя −2"), total penalty capped at
−5. Buttons «Лечить себя» (Разум d20 vs 8/12/16 by severity) and
«Использовать лекарство». Demo toggle «При смерти»: screen darkens, 3-round
clock, «Ты слышишь голоса», rescue buttons appear for allies in the zone.

=== 7. COMBAT (free text) ===
Top-down shore scene at night. Enemies have no attack roll; each has a strike
difficulty (слабый 10, обычный 12, сильный 14, вожак 16+). Intent icons float
above enemy tokens (strike, grab, retreat, call help).
ATTACK: text field «Опиши удар» -> «Я понял так» card: maneuver (удар,
толчок, захват, обезоружить, оглушить, запугать, пленить), aimed body part
if any (+2 difficulty), environment used. Examples to include as demo text:
«Бью по руке, чтобы выбить оружие», «Толкаю его на бочку со смолой».
DEFENSE: when an enemy strikes, a card «Тебя бьют: сила удара 12». Text field
«Опиши, как защищаешься» -> «Я понял так» card: one of Уклониться
(Ловкость), Блокировать (Сила, needs shield or weapon), Стиснуть зубы (no
roll, light wound), Прикрыть союзника (same zone), plus environment used
(+2, only objects that exist in the zone). Demo text: «Прыгаю за бочку и
пережидаю удар». Result: d20 + stat - wound penalties vs difficulty; short
by 1-4 light, 5-9 medium, 10+ or nat 1 heavy; head and torso one step
heavier; body part by d6; light/medium = 1 cell, heavy = 2; max 3 strikes
per hero per round. Animate the wound onto the silhouette. Fate allows a
re-roll with a story cost.

=== 8. INTERROGATION (free text) ===
Dim longhouse cellar, a shackled captive, a torch. Text field «Что ты
говоришь и делаешь?» -> «Я понял так» card: dominant method (убедить,
подкупить, запугать, обмануть, пытка), what is offered or threatened, which
KNOWN fact or item is used as leverage (+2 only if the hero knows it or owns
it). Hero reactions (approving, disgusted, indifferent). A reputation meter
for NPC attitude to the party. The captive's answer is shown as spoken
words with NO truth indicator (rule 4).

=== 9. SETTINGS ===
Personal (phone): звук эффектов, вибрация, размер текста, режим левши,
высокий контраст, «Подсказки новичкам» (default OFF).
Table (TV): громкость эмбиента, музыка угрозы, размер субтитров.
Evening settings: see lobby. There is NO "Save" button on phones.

=== 10. SAVE / LOAD ===
TV start menu «Продолжить сагу» list. Load screen: hero portraits «на месте»
/ «ждёт игрока»; phones show «Это ты?». Then the Oath, then a «Ранее в саге»
recap card. «Сохранить и выйти» needs every player: a consent card
[Согласен][Против] on each phone. Disconnected hero: badge «под управлением
ИИ», on return «Пока тебя не было».

=== 11. HEROES (11 cards: portrait + 4 stats (Сила, Ловкость, Разум, Дух) +
Стойкость cells + gift + action ability + small ⚡ ability) ===
Рагнар ярл 2/2/2/3, Стойкость 3, Голос вождя, Строй клана, ⚡Приказ
Астрид берсерк 4/2/1/2, 5, Закалка, Ярость, ⚡Боевой рёв
Эйрик кузнец 3/1/3/2, 4, Мастеровой, Кузнечная печать, ⚡Укрепить
Сигрид разведчица 1/4/3/1, 2, Лёгкая поступь, Тень ворона, ⚡Петля
Вальд скальд 1/2/4/2, 2, Знаток легенд, Песнь памяти, ⚡Насмешка
Гуннхильд вёльва 1/2/3/3, 2, Травница, Голос предков, ⚡Оберег
Торвальд мореплаватель 2/3/2/2, 3, Чувство моря, Ва-банк, ⚡Попутный ветер
Бьорн охотник 3/3/2/1, 4, Следопыт, Засада, ⚡Чутьё зверя
Лейв вор 2/4/2/1, 3, Ловкие руки, Подмена, ⚡Горсть золы
Хельга жрица Одина 1/1/3/4, 2, Видящая, Прочесть руны, ⚡Руна судьбы
Халльдора щитоносица 4/1/1/3, 5, Стена, Стоять насмерть, ⚡Принять удар
All heroes start with every cell empty (no wounds).

=== SAMPLE DATA ===
Scene "Корабль без команды". Players: Астрид, Эйрик, Сигрид, Вальд.
Narrator: «Корабль скрипит у пирса. В трюме что-то ударяет в доски — раз,
другой.»

OUTPUT: one responsive HTML file, all screens reachable from the top
switcher. Do not invent extra mechanics. Do not add any text labels or
buttons that name map zones (rule 1).
```

## Если Gemini не вместит всё в один файл

Попросите по частям, каждая отдельным файлом:
- «Сделай только часть A: стартовое меню, лобби, клятва, настройки, сохранение».
- «Сделай только часть B: экран СТОЛ и общую карту. Главное: большая подробная карта корабля и карта Хладмарка».
- «Сделай только часть C: экран телефона со всеми вкладками и режимом карты «Зоны / Мир»».
- «Сделай только часть D: бой и допрос со свободным текстом».
