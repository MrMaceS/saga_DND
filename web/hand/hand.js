import { h, clear, s, toast, cells, STAT_NAMES, OUTCOMES } from '../shared/dom.js';
import { api, store } from '../shared/api.js';
import { Socket } from '../shared/socket.js';
import { avatar } from '../shared/avatar.js';
import { renderMap } from '../shared/map.js';

const KEY = 'saga.hand';
const app = document.getElementById('app');
const conn = document.getElementById('conn');
const READER = { off: 'Выкл', rotate: 'По кругу', volunteers: 'Добровольцы' };
const CRUELTY = { restrained: 'Сдержанная', bloody: 'Кровавая' };
const BODY = { head: 'Голова', torso: 'Торс', arm: 'Рука', leg: 'Нога' };
const SEV = { light: 'лёгкое', medium: 'среднее', heavy: 'тяжёлое' };
const PENALTY = { light: -1, medium: -2, heavy: -3 };

let sess = null;              // { code, token }
let state = null, socket = null, heroes = null;
let tab = 'loc';
let draft = '';               // текст в строке ввода сохраняется между перерисовками
let skipUntil = 0;
let exitVote = null;
let shareFor = null, speakMode = null;

const send = (type, payload = {}) => { if (!socket || !socket.send(type, payload)) toast('Нет связи с сервером'); };

// ----------------------------------------------------------- вход
async function boot() {
  const params = new URLSearchParams(location.search);
  const saved = store.get(KEY);
  const codeFromUrl = (params.get('code') || '').toUpperCase();
  if (saved && (!codeFromUrl || saved.code === codeFromUrl)) {
    try { await api.get(`/api/hand/${saved.code}?device_token=${encodeURIComponent(saved.token)}`); sess = saved; connect(); return; }
    catch { store.del(KEY); }
  }
  renderJoin(codeFromUrl);
}

function renderJoin(code = '') {
  clear(app);
  const codeIn = h('input', { id: 'code', value: code, placeholder: 'Код (например K7M2XQ9R)', maxlength: 8, autocapitalize: 'characters', 'aria-label': 'Код сессии' });
  const nameIn = h('input', { id: 'player-name', placeholder: 'Ваше имя', maxlength: 30, 'aria-label': 'Ваше имя' });
  app.append(h('div', { class: 'wrap stack' }, h('h1', { text: 'Сага Мьёльнира' }),
    h('p', { class: 'muted', text: 'Введите код, который показан на Столе.' }), codeIn, nameIn,
    h('button', { class: 'primary', id: 'btn-join', text: 'Присоединиться', onclick: async () => {
      try {
        const c = codeIn.value.trim().toUpperCase();
        const r = await api.post(`/api/sessions/${c}/join`, { player_name: nameIn.value });
        sess = { code: c, token: r.device_token }; store.set(KEY, sess); connect();
      } catch (e) { toast(e.code === 'session_not_found' ? 'Сессия с таким кодом не найдена' : e.message); }
    } })));
}

function connect() {
  if (socket) socket.close();
  socket = new Socket(`/ws/hand/${sess.code}?token=${sess.token}`, {
    onStatus: (ok, code) => {
      conn.classList.toggle('hidden', ok);
      if (!ok && code === 4401) { store.del(KEY); sess = null; toast('Сессия недоступна. Подключитесь заново.'); renderJoin(); }
    },
    onMessage,
  });
  socket.connect();
}

function onMessage(msg) {
  const p = msg.payload;
  if (msg.type === 'hero.state') { state = p; render(); }
  else if (msg.type === 'error') toast(p.message || p.code);
  else if (msg.type === 'roll.public') toast(`${p.hero_name}: ${p.natural} ${p.modifier >= 0 ? '+' : '−'} ${Math.abs(p.modifier)} против ${p.dc}. ${OUTCOMES[p.outcome] || ''}`, 'info', 6000);
  else if (msg.type === 'narration.public' && p.kind === 'cutscene') { skipUntil = Date.now() + 25000; render(); }
  else if (msg.type === 'vote.request' && p.kind === 'exit') { exitVote = p; render(); }
  else if (msg.type === 'session.paused') { exitVote = null; toast('Сага сохранена и на паузе', 'info'); }
}

// ---------------------------------------------------------- рендер
function render() {
  if (!state) return;
  const keep = document.activeElement && document.activeElement.id === 'action-input';
  const st = state.session.status;
  if (st === 'lobby' || st === 'hero_select') { if (!state.me.hero_id) renderHeroSelect(); else renderReady(); }
  else renderPlay();
  if (keep) { const el = document.getElementById('action-input'); if (el) el.focus(); }
}

async function loadHeroes() { if (!heroes) heroes = await api.heroes(); return heroes; }

function statsEl(stats) {
  return h('div', { class: 'stats' }, Object.entries(STAT_NAMES).map(([k, name]) => h('div', { class: 'stat' }, h('b', { text: stats[k] }), h('span', { class: 'muted small', text: name }))));
}

async function renderHeroSelect() {
  const list = await loadHeroes();
  if (!state || state.me.hero_id) return;
  const taken = state.lobby.taken_heroes || {};
  clear(app);
  const box = h('div', { class: 'heroes' });
  for (const hero of list) {
    const by = taken[hero.id];
    box.append(h('div', { class: `card hero-pick${by ? ' taken' : ''}`, 'data-hero': hero.id },
      h('div', { class: 'hero-card' }, avatar(hero.id, hero.name, 56),
        h('div', {}, h('h3', { text: hero.name }), h('div', { class: 'muted', text: hero.title }))),
      statsEl(hero.stats),
      h('div', { class: 'row small', style: 'margin-top:.5em' }, h('span', { class: 'muted', text: 'Стойкость' }), cells(hero.endurance, 0)),
      h('p', { class: 'small' }, h('b', { text: `Дар «${hero.gift.name}»: ` }), hero.gift.text),
      h('p', { class: 'small' }, h('b', { text: `${hero.action_ability.name}: ` }), hero.action_ability.text),
      h('p', { class: 'small' }, h('b', { text: `⚡ ${hero.minor_ability.name}: ` }), hero.minor_ability.text),
      h('p', { class: 'small muted' }, h('b', { text: `Слабость «${hero.weakness.name}»: ` }), hero.weakness.text),
      h('button', { class: 'primary', 'data-pick': hero.id, text: by ? `Занят: ${by}` : 'Выбрать героя', disabled: !!by, onclick: () => claim(hero.id) })));
  }
  app.append(h('div', { class: 'wrap stack' }, h('h2', { text: 'Выберите героя' }), h('p', { class: 'muted', text: `Игрок: ${state.me.player_name}. Героя выбирают из готовых, создавать не нужно.` }), box));
}

async function claim(heroId) {
  try { await api.post(`/api/sessions/${sess.code}/claim`, { hero_id: heroId, device_token: sess.token }); }
  catch (e) { toast(e.code === 'hero_taken' ? 'Этого героя уже выбрали' : e.message); }
}

function renderReady() {
  const hero = state.hero;
  clear(app);
  const me = state.me;
  const holdBtn = h('button', { class: 'oath', id: 'oath', 'aria-label': 'Удерживайте 3 секунды, чтобы скрепить клятву' }, h('span', { text: me.sworn_oath ? '✔' : 'ᛟ' }));
  if (!me.sworn_oath) wireHold(holdBtn);
  const settings = state.session.settings;
  const sel = (key, options, current) => h('select', { 'data-setting': key, 'aria-label': key, onchange: (e) => { send('setting.propose', { key, value: e.target.value }); e.target.value = current; } },
    Object.entries(options).map(([v, label]) => h('option', { value: v, selected: v === current, text: label })));
  const votes = (state.votes || []).map((v) => {
    const mine = v.votes[state.me.hero_id];
    return h('div', { class: 'card', 'data-vote': v.id },
      h('div', { text: `Предложено: ${v.key === 'reader_mode' ? 'Чтец' : v.key === 'cruelty' ? 'Жестокость' : 'Эмбиент'} → ${READER[v.value] || CRUELTY[v.value] || v.value}` }),
      h('div', { class: 'muted small', text: v.rule === 'unanimous' ? 'Нужно согласие всех' : 'Решает большинство' }),
      mine === undefined ? h('div', { class: 'row' },
        h('button', { class: 'primary', text: 'Согласен', onclick: () => send('setting.vote', { vote_id: v.id, agree: true }) }),
        h('button', { text: 'Против', onclick: () => send('setting.vote', { vote_id: v.id, agree: false }) })) : h('div', { class: 'chip', text: mine ? 'Вы согласны' : 'Вы против' }));
  });
  app.append(h('div', { class: 'wrap stack' },
    h('div', { class: 'card hero-card' }, avatar(hero.id, hero.name, 64), h('div', {}, h('h2', { text: hero.name }), h('div', { class: 'muted', text: hero.title }))),
    h('div', { class: 'card' }, statsEl(hero.stats), h('div', { class: 'row', style: 'margin-top:.5em' }, h('span', { class: 'muted', text: 'Стойкость' }), cells(hero.endurance, 0))),
    h('div', { class: 'card stack' }, h('h3', { text: 'Клятва стола' }),
      h('p', { class: 'small' }, '«Я говорю вслух только то, что услышал бы мой герой. Я не подсказываю тем, кто далеко. Тайны моего героя остаются моими.»'),
      holdBtn, h('div', { class: 'muted small', style: 'text-align:center', text: me.sworn_oath ? 'Клятва скреплена' : 'Удерживайте кнопку 3 секунды' })),
    h('div', { class: 'card stack' }, h('h3', { text: 'Настройки вечера' }),
      h('label', {}, 'Чтец (решает большинство)', sel('reader_mode', READER, settings.reader_mode)),
      h('label', {}, 'Жестокость (нужно согласие всех)', sel('cruelty', CRUELTY, settings.cruelty)),
      h('label', {}, 'Эмбиент и музыка (решает большинство)', sel('ambience', { on: 'Включён', off: 'Выключен' }, settings.ambience)),
      settings.reader_mode === 'volunteers' ? h('button', { text: state.reader && state.reader.is_me ? 'Я больше не хочу читать' : 'Хочу читать вслух', onclick: () => send('reader.volunteer', { on: !(state.reader && state.reader.is_me) }) }) : null),
    ...votes,
    h('button', { class: me.ready ? '' : 'primary', id: 'btn-ready', disabled: !me.sworn_oath, text: me.ready ? 'Я не готов' : 'Готов', onclick: async () => {
      try { await api.post(`/api/sessions/${sess.code}/ready`, { device_token: sess.token, is_ready: !me.ready }); } catch (e) { toast(e.message); }
    } }),
    h('p', { class: 'muted small', text: me.sworn_oath ? 'Ждём, пока все будут готовы. Хост начнёт сагу на Столе.' : 'Сначала скрепите клятву.' }),
    h('button', { class: 'ghost', text: 'Сменить героя', disabled: me.ready, onclick: () => { state.me.hero_id = null; renderHeroSelect(); } })));
}

function wireHold(btn) {
  let raf = 0, start = 0;
  const stop = () => { cancelAnimationFrame(raf); start = 0; btn.style.setProperty('--p', 0); };
  const tick = async () => {
    const p = Math.min(100, ((performance.now() - start) / 3000) * 100);
    btn.style.setProperty('--p', p);
    if (p >= 100) {
      start = 0;
      try { await api.post(`/api/sessions/${sess.code}/oath`, { device_token: sess.token }); } catch (e) { toast(e.message); }
      return;
    }
    raf = requestAnimationFrame(tick);
  };
  const begin = (e) => { e.preventDefault(); start = performance.now(); raf = requestAnimationFrame(tick); };
  btn.addEventListener('pointerdown', begin);
  for (const ev of ['pointerup', 'pointerleave', 'pointercancel']) btn.addEventListener(ev, stop);
  btn.addEventListener('keydown', (e) => { if ((e.key === ' ' || e.key === 'Enter') && !start) begin(e); });
  btn.addEventListener('keyup', stop);
}

// ------------------------------------------------------------- игра
function renderPlay() {
  clear(app);
  const hero = state.hero, me = state.me;
  const turnLabel = { idle: 'думаешь', thinking: 'думаешь', action_chosen: 'действие выбрано', turn_ended: 'ход закончен', in_group_action: 'идёшь с товарищем', downed: 'при смерти' }[me.turn_status] || me.turn_status;
  const header = h('div', { class: 'header' }, h('div', { class: 'row' }, avatar(hero.id, hero.name, 44),
    h('div', { class: 'grow' }, h('b', { text: hero.name }), h('div', { class: 'row small' }, cells(hero.endurance, hero.cells_used), h('span', { class: 'muted', text: `Судьба ${hero.fate}` }))),
    h('div', { style: 'text-align:right' }, h('div', { class: 'chip', id: 'turn-chip', text: turnLabel }), h('div', { class: 'muted small', text: `Раунд ${state.session.round_no}` }))));
  const views = { loc: viewLocation, bag: viewBag, saga: viewSaga, body: viewBody };
  const body = h('div', { class: 'wrap stack' });
  if (state.session.status === 'paused') body.append(h('div', { class: 'banner', style: 'padding:.6em', text: 'Сага на паузе. Ждём Стол.' }));
  if (state.session.phase === 'resolving') body.append(h('div', { class: 'chip warn', text: 'Диктор рассказывает…' }));
  body.append(...views[tab]());
  const tabs = h('nav', { class: 'tabs', role: 'tablist' }, [['loc', 'Локация'], ['bag', 'Рюкзак'], ['saga', 'Моя сага'], ['body', 'Тело']].map(([k, label]) =>
    h('button', { class: tab === k ? 'on' : '', role: 'tab', 'data-tab': k, 'aria-selected': tab === k, text: label, onclick: () => { tab = k; render(); } })));
  app.append(header, body, tabs);
}

function messageEl(m) {
  return h('div', { class: `msg ${m.kind || 'public'}` }, m.text);
}

function viewLocation() {
  const v = state.view, out = [];
  out.push(h('div', { class: 'card', id: 'view-card' },
    v.image_url ? h('img', { src: v.image_url, alt: v.zone_name, style: 'width:100%;border-radius:8px' }) : null,
    h('h3', { text: v.zone_name }), h('div', { class: 'muted small', text: v.level ? `Вы знаете об этом месте: уровень ${v.level} из 3` : 'Вы осматриваетесь…' })));
  out.push(h('div', { class: 'card' }, h('div', { class: 'row' }, h('b', { text: 'Тебя слышат:' }),
    state.heard_by.length ? state.heard_by.map((x) => h('span', { class: 'chip', text: x.name.split(' ')[0] })) : h('span', { class: 'muted', text: 'никого рядом' }))));
  // личная карта: имена только у зон, где побывал именно этот герой
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const adj = state.map.adjacency[state.map.current_zone] || [];
  const mine = [{ hero_id: state.hero.id, name: state.hero.name, zone_id: state.map.current_zone },
    ...state.heard_by.map((x) => ({ hero_id: x.hero_id, name: x.name, zone_id: state.map.current_zone }))];
  renderMap(svg, state.map, { currentZone: state.map.current_zone, tokens: mine.slice(0, 3),
    clickable: (z) => adj.includes(z.id) && state.session.phase === 'declaring',
    onZoneClick: (z) => send('move.step', { target_zone: z.id }) });
  out.push(h('div', { class: 'card' }, h('div', { class: 'muted small', text: 'Нажмите на соседнюю зону, чтобы перейти (шаг бесплатный)' }), h('div', { class: 'map-wrap', style: 'height:230px' }, svg)));
  if (state.moved_pending) out.push(h('div', { class: 'chip warn', text: 'Вы доберётесь до нового места в конце раунда' }));
  // известные задачи
  const tasks = h('div', { class: 'stack', id: 'tasks' });
  for (const t of state.tasks) tasks.append(h('div', { class: 'msg', 'data-task': t.id }, h('span', { class: 'badge', text: t.level }), ' ', t.text));
  if (!state.tasks.length) tasks.append(h('div', { class: 'muted', text: 'Вы пока ничего не заметили.' }));
  out.push(h('div', { class: 'card' }, h('h3', { text: 'Что вам известно' }), tasks));
  // лента
  const feed = h('div', { class: 'feed', id: 'feed' }, state.feed.slice(-25).map(messageEl));
  out.push(h('div', { class: 'card' }, h('h3', { text: 'Лента саги' }), feed));
  setTimeout(() => { const f = document.getElementById('feed'); if (f) f.scrollTop = f.scrollHeight; });
  if (state.reader && state.reader.is_me) {
    const last = [...state.feed].reverse().find((m) => m.kind === 'public' || m.kind === 'cutscene');
    out.push(h('div', { class: 'card reader', id: 'reader-block' }, h('div', { class: 'muted small', text: 'Читай вслух' }), last ? last.text : 'Пока читать нечего.'));
  }
  if (Date.now() < skipUntil) out.push(h('button', { text: 'Пропустить кат-сцену', onclick: () => { send('cutscene.skip'); skipUntil = 0; render(); } }));
  for (const c of state.consent_requests) {
    out.push(h('div', { class: 'card recognized', 'data-consent': c.action_id }, h('b', { text: `${c.from_name.split(' ')[0]} зовёт вас` }), h('div', { text: c.intent }),
      h('div', { class: 'row' }, h('button', { class: 'primary', text: 'Присоединиться', onclick: () => send('consent.respond', { action_id: c.action_id, accept: true }) }),
        h('button', { text: 'Отклонить', onclick: () => send('consent.respond', { action_id: c.action_id, accept: false }) }))));
  }
  if (exitVote) out.push(h('div', { class: 'card recognized' }, h('b', { text: 'Сохранить и выйти?' }), h('div', { class: 'small muted', text: 'Нужно согласие всех игроков' }),
    h('div', { class: 'row' }, h('button', { class: 'primary', text: 'Согласен', onclick: () => { send('exit.vote', { agree: true }); exitVote = null; render(); } }),
      h('button', { text: 'Против', onclick: () => { send('exit.vote', { agree: false }); exitVote = null; render(); } }))));
  out.push(...actionBlock());
  return out;
}

function actionBlock() {
  const out = [];
  const pa = state.pending_action;
  const declaring = state.session.phase === 'declaring' && state.session.status === 'playing';
  if (pa && pa.card) out.push(recognizedCard(pa));
  const input = h('textarea', { id: 'action-input', rows: 2, placeholder: 'Что делает герой?', maxlength: 300, disabled: !declaring || state.me.turn_status === 'turn_ended', 'aria-label': 'Что делает герой?',
    oninput: (e) => { draft = e.target.value; } });
  input.value = draft;
  const submit = () => { const t = input.value.trim(); if (!t) return; send('action.submit_text', { raw_text: t }); draft = ''; input.value = ''; };
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } });
  const chips = h('div', { class: 'row wrap', id: 'chips' });
  for (const c of state.chips.story) chips.append(h('button', { class: 'chip', 'data-chip': 'story', text: c, onclick: () => { input.value = draft = c; input.focus(); } }));
  if (state.chips.simple) chips.append(h('button', { class: 'chip', 'data-chip': 'simple', text: state.chips.simple, onclick: () => { input.value = draft = state.chips.simple; input.focus(); } }));
  const others = state.lobby.players.filter((p) => p.hero_id && p.hero_id !== state.hero.id);
  out.push(h('div', { class: 'card stack' }, chips, input,
    h('div', { class: 'row wrap' },
      h('button', { class: 'primary grow', id: 'btn-send', text: 'Отправить', disabled: !declaring, onclick: submit }),
      h('button', { id: 'btn-whisper', text: 'Шепнуть', disabled: !declaring, onclick: () => { speakMode = speakMode === 'whisper' ? null : 'whisper'; render(); } }),
      h('button', { id: 'btn-shout', text: 'Окрикнуть', disabled: !declaring, onclick: () => { speakMode = speakMode === 'shout' ? null : 'shout'; render(); } })),
    speakMode ? speakForm(others) : null));
  const ended = state.me.turn_status === 'turn_ended';
  out.push(h('button', { id: 'btn-end', class: ended ? '' : 'primary', disabled: !declaring && !ended, text: ended ? 'Отменить «Закончить ход»' : 'Закончить ход',
    onclick: () => send(ended ? 'turn.unend' : 'turn.end') }));
  return out;
}

function speakForm(others) {
  const who = h('select', { id: 'speak-target', 'aria-label': 'Кому' }, others.map((p) => h('option', { value: p.hero_id, text: p.hero_name })));
  const text = h('input', { id: 'speak-text', placeholder: speakMode === 'whisper' ? 'Шёпот (только герои в вашей зоне)' : 'Окрик (бросок Духа)', maxlength: 200 });
  return h('div', { class: 'stack' }, who, text, h('button', { id: 'btn-speak-go', text: speakMode === 'whisper' ? 'Прошептать' : 'Крикнуть', onclick: () => {
    if (!text.value.trim()) return;
    send(speakMode === 'whisper' ? 'whisper.send' : 'shout.send', { target_hero: who.value, content: text.value }); speakMode = null; render();
  } }));
}

function recognizedCard(pa) {
  const c = pa.card;
  const body = h('div', { class: 'card recognized stack', id: 'recognized' }, h('b', { text: 'Я понял так' }));
  if (c.needs_clarification) {
    body.append(h('div', { text: c.clarifying_question }), c.alternative ? h('div', { class: 'muted small', text: `Например: ${c.alternative}` }) : null);
  } else if (!c.is_possible) {
    body.append(h('div', { text: c.rejection_reason }), c.alternative ? h('div', { class: 'muted small', text: `Можно: ${c.alternative}` }) : null);
  } else {
    body.append(h('div', {}, h('b', { text: c.label }), c.target ? ` · ${c.target}` : ''));
    body.append(h('div', { class: 'row wrap' },
      c.no_roll ? h('span', { class: 'chip', text: 'без броска' }) : h('span', { class: 'chip', text: `${c.stat}: сложность ${c.difficulty}` }),
      c.move_to ? h('span', { class: 'chip', text: c.cross_location ? 'переход в конце раунда' : 'шаг в соседнюю зону' }) : null,
      ...c.consent_from.map((x) => h('span', { class: 'chip warn', text: `нужно согласие: ${x.name.split(' ')[0]}` })),
      c.side_action ? h('span', { class: 'chip', text: `${c.side_action.type === 'shout' ? 'окрик' : 'шёпот'} → ${(c.side_action.target_name || '').split(' ')[0]}` }) : null));
  }
  const canConfirm = pa.status === 'draft' && !c.needs_clarification && c.is_possible;
  body.append(h('div', { class: 'row' },
    canConfirm ? h('button', { class: 'primary', id: 'btn-confirm', text: 'Подтвердить', onclick: () => send('action.confirm', { action_id: pa.id }) }) : null,
    pa.status === 'confirmed' ? h('span', { class: 'chip ok', text: 'Подтверждено' }) : null,
    h('button', { id: 'btn-cancel', text: pa.status === 'confirmed' ? 'Отменить' : 'Исправить', onclick: () => send('action.cancel') })));
  return body;
}

function viewBag() {
  const slots = h('div', { class: 'stats', style: 'grid-template-columns:repeat(2,1fr)', id: 'slots' });
  for (let i = 0; i < 4; i++) {
    const item = state.hero.inventory[i];
    slots.append(h('div', { class: `slot${item ? ' full' : ''}`, 'data-slot': i, text: item || 'пусто' }));
  }
  const clues = state.clues.length ? state.clues.map((c) => h('div', { class: 'msg', text: c.text })) : [h('div', { class: 'muted', text: 'Записок и улик пока нет.' })];
  return [h('div', { class: 'card stack' }, h('h3', { text: 'Рюкзак (4 слота)' }), slots, h('div', { class: 'muted small', text: 'Передача предметов и сундук появятся с длинным домом.' })),
    h('div', { class: 'card stack', id: 'clues' }, h('h3', { text: 'Записки и улики' }), ...clues)];
}

function viewSaga() {
  const hero = state.hero, out = [];
  out.push(h('div', { class: 'card stack' }, h('h3', { text: 'Цель' }), h('div', { text: hero.goal.text }),
    h('div', { class: 'stack' }, hero.goal.steps.map((step, i) => h('div', { class: `chip ${i < hero.goal.progress ? 'ok' : ''}`, text: `${i + 1}. ${step}` })))));
  const secret = (label, sec) => h('div', { class: 'card', 'data-secret': label }, h('b', { text: label }), sec.state === 'sealed'
    ? h('div', { class: 'muted', text: '✉ Запечатано. Что-то с тобой не так…' }) : h('div', { text: sec.text }), sec.state === 'known' ? h('div', { class: 'muted small', text: 'Знает: только ты' }) : null);
  out.push(secret('Тайна судьбы', hero.secrets.story), secret('Личная тайна', hero.secrets.personal));
  out.push(h('div', { class: 'card stack' }, h('h3', { text: 'Слабость' }), h('div', {}, h('b', { text: hero.weakness.name + '. ' }), hero.weakness.text)));
  const journal = h('div', { class: 'stack', id: 'journal' });
  const facts = [...state.tasks.map((t) => ({ id: `task:${t.id}:${t.level}`, text: t.text, level: t.level })), ...state.facts.filter((f) => f.source !== 'whisper' || true).map((f) => ({ id: f.id, text: f.text, level: f.level }))];
  for (const f of facts) {
    journal.append(h('div', { class: 'msg', 'data-fact': f.id }, h('span', { class: 'badge', text: f.level }), ' ', f.text, ' ',
      state.heard_by.length ? h('button', { class: 'chip', text: 'Поделиться', onclick: () => { shareFor = f.id; render(); } }) : null));
  }
  if (!facts.length) journal.append(h('div', { class: 'muted', text: 'Журнал пуст.' }));
  out.push(h('div', { class: 'card stack' }, h('h3', { text: 'Журнал знаний' }), journal,
    h('div', { class: 'muted small', text: 'Поделиться можно только с теми, кто в вашей зоне.' })));
  if (shareFor) out.push(h('div', { class: 'card recognized stack', id: 'share-box' }, h('b', { text: 'С кем поделиться?' }),
    ...state.heard_by.map((x) => h('button', { text: x.name, onclick: () => { send('fact.share', { fact_id: shareFor, recipients: [x.hero_id] }); shareFor = null; render(); } })),
    h('button', { class: 'ghost', text: 'Отмена', onclick: () => { shareFor = null; render(); } })));
  return out;
}

function silhouette(wounds) {
  const hurt = (part, side) => wounds.some((w) => w.body_part === part && (!side || !w.side || w.side === side));
  const cls = (part, side) => `part${hurt(part, side) ? ' hurt' : ''}`;
  return s('svg', { class: 'silhouette', viewBox: '0 0 150 300', role: 'img', 'aria-label': 'Силуэт героя' },
    s('circle', { class: cls('head'), cx: 75, cy: 32, r: 24, 'data-part': 'head' }),
    s('rect', { class: cls('torso'), x: 48, y: 62, width: 54, height: 100, rx: 10, 'data-part': 'torso' }),
    s('rect', { class: cls('arm', 'left'), x: 20, y: 66, width: 22, height: 90, rx: 9, 'data-part': 'arm-left' }),
    s('rect', { class: cls('arm', 'right'), x: 108, y: 66, width: 22, height: 90, rx: 9, 'data-part': 'arm-right' }),
    s('rect', { class: cls('leg'), x: 50, y: 168, width: 22, height: 120, rx: 9, 'data-part': 'leg-left' }),
    s('rect', { class: cls('leg'), x: 78, y: 168, width: 22, height: 120, rx: 9, 'data-part': 'leg-right' }));
}

function viewBody() {
  const hero = state.hero;
  const list = hero.wounds.length
    ? hero.wounds.map((w) => h('div', { class: 'msg private', text: `${BODY[w.body_part]}: ${SEV[w.severity]} (${PENALTY[w.severity]})` }))
    : [h('div', { class: 'chip ok', text: 'Ранений нет. Вы здоровы.' })];
  return [h('div', { class: 'card stack' }, h('h3', { text: 'Тело' }), silhouette(hero.wounds),
    h('div', { class: 'row' }, h('span', { class: 'muted', text: 'Стойкость' }), cells(hero.endurance, hero.cells_used)),
    h('div', { class: 'muted small', text: `Общий штраф от ранений: ${hero.penalty} (не ниже −5)` }), ...list,
    hero.downed ? h('div', { class: 'chip bad', text: 'Вы при смерти. Союзник может вас спасти.' }) : null)];
}

boot();
