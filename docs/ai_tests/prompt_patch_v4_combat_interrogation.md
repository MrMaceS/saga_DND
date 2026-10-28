# Патч v4: свободное описание защиты, атаки и допроса

Принцип тот же: игрок пишет что угодно, Gemini превращает это в структуру, Python проверяет и считает, диктор описывает результат. Игрок не может придумать несуществующий предмет и не может отменить удар словами.

## Дополнение к схеме основного интерпретатора (атака)
Добавить поля:
```
"maneuver": "strike|shove|grapple|disarm|stun|intimidate|capture|custom"|null,
"aim": "head|torso|arm|leg"|null,
"uses_environment": [str]
```
Правила:
```
13. Если игрок целится в часть тела, запиши aim. Прицел усложняет проверку (сервер).
14. Объекты окружения (бочка, смола, канат) разрешены, только если их id есть
    в контексте зоны (context.environment). Иначе is_possible=false и alternative.
15. maneuver выбирай по смыслу описания. Не выдумывай уникальных приёмов.
```

## Отдельный режим: защита
Включается, когда сервер присылает `"mode":"defense"` и `"incoming_strike"`.

```
Верни ОДИН JSON:
{
 "mode":"defense",
 "hero_id": str,
 "defense_type": "dodge|block|endure|cover_ally|custom",
 "stat": "agility|strength|spirit",
 "target_hero": str|null,
 "uses_environment": [str],
 "uses_items": [str],
 "needs_clarification": bool,
 "clarifying_question": str|null,
 "is_possible": bool,
 "rejection_reason": str|null,
 "alternative": str|null
}
Правила:
- dodge = Ловкость; block = Сила, нужен щит или оружие в items героя;
  endure = без броска; cover_ally = только герой из той же зоны.
- Защита не отменяет удар и не убивает врага. Если игрок описывает такое,
  is_possible=false и alternative.
- Бонус от окружения и предметов НЕ указывай числом, считает сервер
  (+2 за подходящий объект, максимум +2 от окружения, все источники вместе не больше +5).
- Описание без понятного способа («как-нибудь») = needs_clarification.
```

## Отдельный режим: допрос
Включается, когда сервер присылает `"mode":"interrogation"`, `target_entity` (пленный) и список `known_facts_of_hero`.

```
Верни ОДИН JSON:
{
 "mode":"interrogation",
 "hero_id": str,
 "target_entity": str,
 "method": "persuade|bribe|intimidate|deceive|torture",
 "secondary_method": str|null,
 "leverage": [{"type":"fact|item|threat","ref":str}],
 "offer": str|null,
 "needs_clarification": bool,
 "clarifying_question": str|null,
 "is_possible": bool,
 "rejection_reason": str|null,
 "alternative": str|null
}
Правила:
- Один бросок за допрос. Выбери главный метод по смыслу; побочный только для окраски.
- leverage типа fact разрешён, только если ref есть в known_facts_of_hero.
  Предмет разрешён, только если он в items героя. Угрозу запиши текстом.
- Ты НИКОГДА не решаешь, правду ли скажет пленный. Это решает сервер скрыто.
- Нельзя заставить пленного выдать то, чего он не знает.
```

## Что считает сервер
- Допрос: d20 + стат метода (у героя есть свой стиль допроса из карточки) против сложности пленного. Лидерство факта или предмета даёт +2.
- Надёжность ответа (правда или ложь) определяется скрыто: убеждение и лесть надёжнее, пытка менее надёжна. Игрок и диктор этого не видят.
- Последствия идут в «книгу саги»: отношение NPC, реакции героев (Вальд и Гуннхильд против пытки, Астрид и Бьорн безразличны), Вера и репутация.

## Тесты

Защита (контекст: сила удара 12, в зоне есть бочка со смолой, у Астрид топор и факел):
| Игрок пишет | Ожидаем |
|---|---|
| Прыгаю за бочку и пережидаю удар | `dodge`, `agility`, `uses_environment:[barrel]` |
| Принимаю удар на топор | `block`, `strength`, `uses_items:[топор]` |
| Закрываю собой Эйрика | `cover_ally`, `target_hero: eirik` (только если он в зоне) |
| Просто выдерживаю | `endure` |
| Отбиваю удар так, что враг падает замертво | `is_possible:false`, alternative |
| Прячусь за каменной стеной | `is_possible:false` (стены нет в контексте) |
| Как-нибудь защищусь | `needs_clarification:true` |

Атака:
| Игрок пишет | Ожидаем |
|---|---|
| Бью по руке, чтобы выбить оружие | `attack`, `maneuver: disarm`, `aim: arm` |
| Толкаю его на бочку со смолой | `maneuver: shove`, `uses_environment:[barrel]` |
| Хватаю за горло и душу | `maneuver: grapple`, `aim: torso` или `null` |

Допрос (пленный `captive_1`, герой знает факт `ship_crest`, предмета «золото» нет):
| Игрок пишет | Ожидаем |
|---|---|
| Показываю клеймо с корабля и говорю, что знаю, чей он | `deceive` или `persuade`, `leverage: fact ship_crest` |
| Предлагаю золото за правду | `bribe`, но золота нет в items → `is_possible:false`, alternative |
| Ломаю ему палец, пока не заговорит | `torture` |
| Ласково говорю, что он не виноват, но давлю взглядом | `persuade`, `secondary: intimidate` |
| Пусть скажет, где ярл, и сколько у него золота | один главный вопрос, без требования невозможного |
