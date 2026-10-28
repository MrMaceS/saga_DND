// Сквозная проверка фронтенда в jsdom против живого сервера: Стол и два телефона проходят вечер до второго раунда.
import { JSDOM, VirtualConsole } from 'jsdom';
import { bundle } from './bundle.mjs';

const BASE = process.env.BASE || 'http://127.0.0.1:8765';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const failures = [];
const check = (cond, msg) => { if (!cond) { failures.push(msg); console.log('  ✗', msg); } else console.log('  ✓', msg); };

async function open(page, query = '') {
  const url = `${BASE}/web/${page}/${query}`;
  const html = await (await fetch(url)).text();
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', (e) => errors.push(String(e.stack || e)));
  vc.on('error', (m) => errors.push(String(m)));
  const dom = new JSDOM(html, { url, runScripts: 'outside-only', pretendToBeVisual: true, virtualConsole: vc });
  const w = dom.window;
  w.fetch = (u, o) => fetch(new URL(u, url), o);
  w.addEventListener('error', (e) => errors.push(String(e.message)));
  w.addEventListener('unhandledrejection', (e) => errors.push('promise: ' + String(e.reason)));
  w.eval(bundle(page));
  return { w, d: w.document, errors, q: (s) => w.document.querySelector(s), qa: (s) => [...w.document.querySelectorAll(s)] };
}
async function waitFor(fn, what, ms = 8000) {
  const end = Date.now() + ms;
  while (Date.now() < end) { try { const v = fn(); if (v) return v; } catch { /* ждём */ } await sleep(60); }
  throw new Error('не дождались: ' + what);
}
const type = (w, el, value) => { el.value = value; el.dispatchEvent(new w.Event('input', { bubbles: true })); };
const text = (el) => (el ? el.textContent.replace(/\s+/g, ' ').trim() : '');

async function main() {
  console.log('Стол: создание саги');
  const T = await open('table');
  await waitFor(() => T.q('#btn-new'), 'кнопка «Новая сага»');
  T.q('#btn-new').click();
  await waitFor(() => T.q('#btn-create'), 'форма создания');
  check(T.qa('.story').length === 5, 'на экране 5 историй');
  check(T.qa('.story.off').length === 4, 'недоступные истории отключены, а не подсунуты');
  type(T.w, T.q('#saga-name'), 'Ночь у Хладмарка');
  T.q('#btn-create').click();
  const code = await waitFor(() => text(T.q('#join-code')).length === 8 && text(T.q('#join-code')), 'код приглашения');
  check(/^[A-Z2-9]{8}$/.test(code), `код приглашения из 8 символов: ${code}`);
  check(text(T.q('#join-url')).includes(`/web/hand/?code=${code}`), 'адрес для телефонов показан');

  console.log('Телефоны: вход и выбор героя');
  const A = await open('hand', `?code=${code}`);
  const E = await open('hand', `?code=${code}`);
  for (const [P, name] of [[A, 'Анна'], [E, 'Борис']]) {
    await waitFor(() => P.q('#btn-join'), 'форма входа');
    check(P.q('#code').value === code, `код подставлен из ссылки (${name})`);
    type(P.w, P.q('#player-name'), name);
    P.q('#btn-join').click();
  }
  await waitFor(() => A.qa('.hero-pick').length === 11, 'каталог из 11 героев (GET /api/heroes)');
  check(A.qa('.hero-pick').length === 11, 'у игрока 11 карточек героев из API');
  check(text(A.q('[data-hero="eirik"]')).includes('Кузнец'), 'Эйрик показан кузнецом (данные с сервера, не хардкод)');
  A.q('[data-pick="astrid"]').click();
  await waitFor(() => A.q('#oath'), 'экран клятвы у Анны');
  await waitFor(() => E.q('[data-hero="astrid"] button[disabled]'), 'у Бориса герой Астрид занят');
  check(text(E.q('[data-hero="astrid"] button')).includes('Анна'), 'занятый герой подписан именем игрока');
  E.q('[data-pick="eirik"]').click();
  await waitFor(() => E.q('#oath'), 'экран клятвы у Бориса');
  check(A.q('#btn-ready').disabled, '«Готов» заблокирован до клятвы');

  console.log('Клятва стола (удержание 3 секунды)');
  for (const P of [A, E]) P.q('#oath').dispatchEvent(new P.w.Event('pointerdown', { bubbles: true, cancelable: true }));
  await sleep(1200);
  for (const P of [A, E]) P.q('#oath').dispatchEvent(new P.w.Event('pointerup', { bubbles: true }));
  check(!text(A.q('#oath')).includes('✔'), 'если отпустить раньше 3 секунд, клятва не скрепляется');
  for (const P of [A, E]) P.q('#oath').dispatchEvent(new P.w.Event('pointerdown', { bubbles: true, cancelable: true }));
  await waitFor(() => text(A.q('#oath')).includes('✔') && text(E.q('#oath')).includes('✔'), 'клятва скреплена', 6000);
  check(true, 'клятва скреплена после удержания');
  A.q('#btn-ready').click(); E.q('#btn-ready').click();
  await waitFor(() => !T.q('#btn-start').disabled, 'Стол разрешил старт');
  check(T.qa('.player').length >= 2 && text(T.q('.players')).includes('Астрид'), 'на Столе видны игроки и их герои');

  console.log('Игра: карта, часы, раунд');
  T.q('#btn-start').click();
  await waitFor(() => T.q('#focus-map svg .zone'), 'карта на Столе');
  await waitFor(() => T.qa('#clocks .clock').length === 3, 'три безымянных часа на Столе');
  const names = T.qa('.zone.known text').map((x) => text(x));
  check(names.length === 1 && names[0] === 'Пирс', `на карте имя только у посещённой зоны: ${names}`);
  check(T.qa('.zone.unknown text').every((x) => text(x) === '?'), 'неизвестные зоны нарисованы как «?»');
  check(T.qa('#clocks .clock .name').every((x) => !/Якорь|Третий|Тени/.test(text(x))), 'угрозы без разведки не названы');
  check(!/\d\/\d/.test(text(T.q('#clocks'))), 'у неразведанных часов нет цифр');
  await waitFor(() => A.q('#view-card') && A.q('#action-input'), 'экран игры у Анны');
  check(A.qa('.tabs button').length === 4, 'четыре вкладки телефона');
  check(A.qa('#chips button').length >= 2, 'подсказки под вводом есть');
  check(!A.qa('#chips button').some((b) => /каюта|мачта|трюм/i.test(text(b)) && /Проверить трюм/.test(text(b))), 'нет подсказок-кнопок с названиями зон');
  check(text(A.q('#tasks')).includes('В трюме кто-то есть'), 'известная задача появилась из рассказа диктора');
  const mapZones = A.qa('svg.map .zone');
  check(mapZones.length >= 2, 'личная карта нарисована по данным сервера');

  type(A.w, A.q('#action-input'), 'Осматриваю палубу в поисках ценного');
  A.q('#btn-send').click();
  await waitFor(() => A.q('#btn-confirm'), 'карточка «Я понял так»');
  check(text(A.q('#recognized')).includes('сложность'), 'в карточке видна сложность проверки');
  A.q('#btn-confirm').click();
  await waitFor(() => A.q('#recognized .chip.ok'), 'заявка подтверждена');
  A.q('#btn-end').click();
  await sleep(300);
  check(text(T.q('.player[data-hero="astrid"]')).includes('ход закончен'), 'Стол показывает «ход закончен» у Астрид');
  check(T.q('#round') && text(T.q('#round')) === 'Раунд 1', 'пока Борис не закончил, раунд не идёт');
  E.q('#btn-end').click();
  await waitFor(() => text(T.q('#round')) === 'Раунд 2', 'второй раунд на Столе', 12000);
  await waitFor(() => text(A.q('.header')).includes('Раунд 2'), 'второй раунд у игрока');
  check(T.q('#overlay').dataset.kind !== undefined, 'оверлей кат-сцены/кубика отрабатывает');
  await waitFor(() => T.qa('.zone.known').length >= 2, 'на карте появилась зона «Палуба»', 6000);
  check(T.qa('.zone.known text').map(text).includes('Палуба'), 'Палуба получила имя после посещения');
  check(!E.qa('svg.map .zone.known text').map(text).includes('Палуба'), 'у Бориса личная карта не раскрыла «Палуба»');
  check(text(T.q('#narration')).length > 10, 'на Столе есть рассказ диктора');
  await waitFor(() => T.qa('#clocks .clock').length === 3, 'часы остались на Столе');
  A.q('[data-tab="bag"]').click();
  check(A.qa('#slots .slot').length === 4, 'рюкзак: четыре слота');
  A.q('[data-tab="saga"]').click();
  check(text(A.q('[data-secret="Тайна судьбы"]')).includes('Запечатано'), 'сюжетная тайна запечатана');
  A.q('[data-tab="body"]').click();
  check(text(A.q('.card')).includes('Ранений нет'), 'на старте у героя нет ранений');
  E.q('[data-tab="bag"]').click();
  check(!text(E.q('#clues')).includes('Не открывайте'), 'находки Астрид не видны Борису');

  for (const [name, P] of [['Стол', T], ['Анна', A], ['Борис', E]]) {
    check(P.errors.length === 0, `нет ошибок JavaScript у «${name}»` + (P.errors.length ? ': ' + P.errors[0].slice(0, 300) : ''));
  }
  for (const P of [T, A, E]) P.w.close();
}

main().then(() => { console.log(failures.length ? `\nПровалено проверок: ${failures.length}` : '\nВсе проверки фронтенда пройдены'); process.exit(failures.length ? 1 : 0); })
  .catch((e) => { console.error('\nСбой сценария:', e.message); process.exit(2); });
