import { h, clear, toast, cells, OUTCOMES, STAT_NAMES } from '../shared/dom.js';
import { api, store } from '../shared/api.js';
import { Socket } from '../shared/socket.js';
import { avatar } from '../shared/avatar.js';
import { renderMap } from '../shared/map.js';
import { clockEl } from '../shared/clocks.js';

const KEY = 'saga.table';
const app = document.getElementById('app');
const overlay = document.getElementById('overlay');
const conn = document.getElementById('conn');
const READER = { off: 'Выкл', rotate: 'По кругу', volunteers: 'Добровольцы' };
const CRUELTY = { restrained: 'Сдержанная', bloody: 'Кровавая' };

let sess = store.get(KEY);          // { code, token }
let state = null, socket = null, mapData = null, mapKey = '', soundOn = true;
let narration = [];
let timers = [];

const headers = () => ({ 'X-Table-Token': sess.token });
const heroName = (id) => (state && state.players && (state.players.find((p) => p.hero_id === id) || {}).hero_name) || id;

// ------------------------------------------------------------- старт
async function boot() {
  if (sess) {
    try { state = await api.get(`/api/table/${sess.code}`, headers()); connect(); render(); return; }
    catch { store.del(KEY); sess = null; }
  }
  showStart();
}

function showStart() {
  if (socket) { socket.close(); socket = null; }
  state = null;
  clear(app);
  const screen = h('div', { class: 'screen stack' }, h('h1', { text: 'Сага Мьёльнира · Стол' }),
    h('p', { class: 'muted', text: 'Этот экран показывают всем: карта, часы угроз и рассказ диктора.' }));
  const buttons = h('div', { class: 'row wrap' },
    h('button', { class: 'primary', id: 'btn-new', text: 'Новая сага', onclick: showCreate }));
  screen.append(buttons);
  const resumeBox = h('div', { class: 'stack' });
  screen.append(h('h2', { text: 'Продолжить сагу' }), resumeBox);
  api.resumable().then((list) => {
    if (!list.length) resumeBox.append(h('p', { class: 'muted', text: 'Сохранённых саг пока нет.' }));
    for (const s of list) {
      resumeBox.append(h('div', { class: 'card row' },
        h('div', { class: 'grow' }, h('b', { text: s.name }), h('div', { class: 'muted small', text: `Код ${s.code} · раунд ${s.round_no} · игроков ${s.players}` })),
        h('button', { text: 'Продолжить', onclick: () => resume(s.code) })));
    }
  }).catch(() => resumeBox.append(h('p', { class: 'muted', text: 'Не удалось получить список сохранений.' })));
  app.append(screen);
}

async function resume(code) {
  try {
    const r = await api.post(`/api/sessions/${code}/resume`);
    sess = { code: r.join_code, token: r.table_token }; store.set(KEY, sess);
    state = await api.get(`/api/table/${sess.code}`, headers());
    connect(); render();
  } catch (e) { toast(e.message); }
}

async function showCreate() {
  clear(app);
  let stories = [];
  try { stories = await api.stories(); } catch { toast('Не удалось загрузить истории'); }
  let selected = (stories.find((s) => s.playable) || {}).id, count = 4;
  const name = h('input', { id: 'saga-name', value: 'Ночь у Хладмарка', maxlength: 60, 'aria-label': 'Название сессии' });
  const hint = h('p', { class: 'muted small' });
  const cards = h('div', { class: 'stories' });
  const stepper = h('div', { class: 'stepper', role: 'group', 'aria-label': 'Число игроков' });
  const draw = () => {
    clear(cards); clear(stepper);
    for (const s of stories) {
      cards.append(h('div', { class: `story${s.id === selected ? ' sel' : ''}${s.playable ? '' : ' off'}`, 'data-story': s.id,
        tabindex: 0, role: 'button', 'aria-disabled': !s.playable,
        onclick: () => { if (s.playable) { selected = s.id; draw(); } } },
        h('b', { text: s.title }), h('div', { class: 'muted small', text: s.genre }),
        h('p', { class: 'small', text: s.blurb }),
        h('div', { class: 'chip', text: s.playable ? `Рекомендуется ${s.recommended[0]}–${s.recommended[1]} · играть можно ${s.allowed[0]}–${s.allowed[1]}` : 'Скоро' })));
    }
    for (let n = 2; n <= 10; n++) stepper.append(h('button', { class: n === count ? 'sel' : '', text: String(n), onclick: () => { count = n; draw(); } }));
    const st = stories.find((s) => s.id === selected);
    hint.textContent = st ? `Сценарий подстроится под ${count} игроков. Сложность и число врагов не меняются.` : '';
  };
  draw();
  app.append(h('div', { class: 'screen stack' },
    h('h1', { text: 'Создать сагу' }), h('label', {}, 'Название сессии', name), h('h2', { text: 'История' }), cards,
    h('h2', { text: 'Количество игроков' }), stepper, hint,
    h('div', { class: 'row' }, h('button', { class: 'ghost', text: 'Назад', onclick: showStart }),
      h('button', { class: 'primary', id: 'btn-create', text: 'Создать сессию', onclick: async () => {
        try {
          const r = await api.post('/api/sessions', { name: name.value, story_id: selected, player_count: count });
          sess = { code: r.join_code, token: r.table_token }; store.set(KEY, sess);
          state = await api.get(`/api/table/${sess.code}`, headers());
          connect(); render();
        } catch (e) { toast(e.message); }
      } }))));
}

// -------------------------------------------------------------- сеть
function connect() {
  if (socket) socket.close();
  socket = new Socket(`/ws/table/${sess.code}?token=${sess.token}`, {
    onStatus: (ok, code) => {
      conn.classList.toggle('hidden', ok);
      if (!ok && code === 4401) { store.del(KEY); sess = null; toast('Токен Стола недействителен'); showStart(); }
    },
    onMessage: onMessage,
  });
  socket.connect();
}

function onMessage(msg) {
  const p = msg.payload;
  if (msg.type === 'table.state') { state = p; render(); }
  else if (msg.type === 'narration.public') { narration.push(p); narration = narration.slice(-6); updateNarration(); }
  else if (msg.type === 'cutscene.play') playCutscene(p);
  else if (msg.type === 'cutscene.skip') hideOverlay();
  else if (msg.type === 'roll.public') showDice(p);
  else if (msg.type === 'vote.request') toast(p.text || 'Идёт голосование', 'info');
  else if (msg.type === 'session.paused') toast('Сага сохранена и поставлена на паузу', 'info');
}

// ------------------------------------------------------------ рендер
function render() {
  if (!state) return;
  const status = state.session.status;
  if (status === 'lobby' || status === 'hero_select') renderLobby();
  else renderPlay();
  if (status === 'paused') showPause(); else if (overlay.dataset.kind === 'pause') hideOverlay();
}

function settingsView(st) {
  const s = st.session.settings || {};
  return h('div', { class: 'row wrap' },
    h('span', { class: 'chip', text: `Чтец: ${READER[s.reader_mode] || s.reader_mode}` }),
    h('span', { class: 'chip', text: `Жестокость: ${CRUELTY[s.cruelty] || s.cruelty}` }),
    h('span', { class: 'chip', text: `Эмбиент: ${s.ambience === 'on' ? 'вкл' : 'выкл'}` }));
}

function renderLobby() {
  clear(app);
  const url = `${location.origin}/web/hand/?code=${state.session.code}`;
  const players = state.lobby.players;
  const allReady = players.length >= 2 && players.every((p) => p.hero_id && p.ready && p.sworn_oath);
  const reason = players.length < 2 ? 'Нужно минимум 2 игрока' : (players.every((p) => p.hero_id) ? 'Ждём, пока все скрепят клятву и нажмут «Готов»' : 'Не все выбрали героев');
  const list = h('div', { class: 'players' });
  for (const p of players) {
    list.append(h('div', { class: 'player', 'data-player': p.player_name },
      p.hero_id ? avatar(p.hero_id, p.hero_name, 44) : h('span', { class: 'avatar', style: 'width:44px;height:44px;display:inline-block' }),
      h('div', { class: 'grow' }, h('b', { text: p.player_name }), h('div', { class: 'muted small', text: p.hero_name || 'выбирает героя…' })),
      h('span', { class: `chip ${p.sworn_oath ? 'ok' : ''}`, text: p.sworn_oath ? 'клятва' : 'без клятвы' }),
      h('span', { class: `chip ${p.ready ? 'ok' : ''}`, text: p.ready ? 'готов' : 'не готов' })));
  }
  for (let i = players.length; i < state.session.player_count; i++) list.append(h('div', { class: 'player muted', text: 'Ожидание игрока…' }));
  const votes = (state.votes || []).map((v) => h('div', { class: 'chip warn', text: `Голосование: ${v.key} → ${v.value} (${Object.values(v.votes).filter(Boolean).length} за)` }));
  app.append(h('div', { class: 'screen stack' },
    h('h1', { text: state.session.name }), h('div', { class: 'muted', text: state.session.story_title }),
    h('div', { class: 'card stack' }, h('div', { class: 'muted', text: 'Код приглашения' }),
      h('div', { class: 'big-code', id: 'join-code', text: state.session.code }),
      h('div', {}, 'Игроки открывают на телефоне: ', h('b', { id: 'join-url', text: url })),
      h('div', { class: 'muted small', text: 'Телефоны и ноутбук должны быть в одной сети Wi-Fi. Порт 8000 должен быть открыт в файрволе.' })),
    h('h2', { text: `Игроки ${players.length} из ${state.session.player_count}` }), list,
    h('h2', { text: 'Настройки вечера' }), settingsView(state), ...votes,
    h('div', { class: 'row' },
      h('button', { class: 'primary', id: 'btn-start', text: 'Начать сагу', disabled: !allReady, onclick: async () => {
        try { await api.post(`/api/sessions/${sess.code}/start`, {}, headers()); } catch (e) { toast(e.message); }
      } }), allReady ? null : h('span', { class: 'muted', text: reason }))));
}

function renderPlay() {
  const st = state;
  const tokens = (st.players || []).filter((p) => p.zone_id).map((p) => ({ hero_id: p.hero_id, name: p.hero_name, zone_id: p.zone_id, wounded: p.cells_used > 0 }));
  clear(app);
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const mapBox = h('div', { class: 'map-wrap focus', id: 'focus-map' }, svg);
  const focus = (st.tiles && st.tiles[0]) ? st.tiles[0].name : '';
  const clocks = h('div', { class: 'clocks', id: 'clocks' });
  const players = h('div', { class: 'stack', id: 'players' });
  for (const p of st.players || []) {
    players.append(h('div', { class: 'player', 'data-hero': p.hero_id },
      avatar(p.hero_id, p.hero_name, 38),
      h('div', { class: 'grow' }, h('b', { text: p.hero_name }), h('div', { class: 'muted small', text: p.player_name })),
      cells(p.endurance, p.cells_used),
      h('span', { class: `chip ${p.turn_status === 'turn_ended' ? 'ok' : p.away ? 'bad' : ''}`, text: p.away ? 'нет связи' : p.turn_label })));
  }
  const tiles = h('div', { class: 'tiles', id: 'tiles' });
  for (const t of st.tiles || []) {
    tiles.append(h('div', { class: 'tile' }, h('b', { text: t.name }), ...t.hero_ids.map((id) => avatar(id, heroName(id), 28))));
  }
  const reader = st.reader ? h('span', { class: 'chip', text: `📖 Читает вслух: ${heroName(st.reader)}` }) : null;
  const top = h('div', { class: 'top' },
    h('h2', { style: 'margin:0', text: `${st.session.name} · ${focus}` }),
    h('span', { class: 'chip', id: 'round', text: `Раунд ${st.session.round_no}` }),
    h('span', { class: `chip ${st.session.phase === 'resolving' ? 'warn' : ''}`, text: st.session.phase === 'resolving' ? 'Диктор рассказывает…' : 'Игроки решают' }),
    reader, st.split ? h('span', { class: 'banner', text: 'Отряд разделён. Говорите только с теми, кто рядом' }) : null,
    h('span', { class: 'grow' }),
    h('button', { id: 'btn-save', text: 'Сохранить', disabled: st.session.phase !== 'declaring', title: st.session.phase !== 'declaring' ? 'Сохранение после раунда' : '', onclick: saveNow }),
    h('button', { id: 'btn-exit', text: 'Сохранить и выйти', onclick: exitRequest }),
    h('button', { id: 'btn-sound', class: 'ghost', text: soundOn ? '🔊' : '🔇', 'aria-label': 'Звук', onclick: () => { soundOn = !soundOn; render(); } }));
  const narr = h('div', { class: 'narr', id: 'narration', 'aria-live': 'polite' });
  app.append(h('div', { class: 'play' }, top, mapBox,
    h('div', { class: 'side' }, h('div', { class: 'card' }, h('h3', { text: 'Угрозы' }), clocks), h('div', { class: 'card' }, h('h3', { text: 'Отряд' }), players)),
    tiles, narr));
  drawMap(svg, tokens, clocks);
  updateNarration();
}

function drawMap(svg, tokens, clocksEl) {
  const paint = () => {
    if (!mapData) return;
    renderMap(svg, mapData, { tokens });
    clear(clocksEl);
    if (!mapData.clocks.length) clocksEl.append(h('div', { class: 'muted small', text: 'Пока всё тихо. Или вы ещё ничего не заметили.' }));
    for (const c of mapData.clocks) clocksEl.append(clockEl(c));
  };
  paint();
  api.tableMap(sess.code, sess.token).then((m) => { mapData = m; if (svg.isConnected) paint(); }).catch(() => {});
}

function updateNarration() {
  const el = document.getElementById('narration');
  if (!el) return;
  clear(el);
  const last = narration.length ? narration[narration.length - 1] : (state && state.feed && state.feed.length ? state.feed[state.feed.length - 1] : null);
  if (!last) { el.append(h('span', { class: 'muted', text: 'Диктор ждёт ваших решений.' })); return; }
  el.append(last.hero_id ? h('span', { class: 'who', text: heroName(last.hero_id) }) : null, last.text);
}

async function saveNow() {
  try { await api.post(`/api/saves/${sess.code}/manual`, {}, headers()); toast('Сага сохранена', 'info'); }
  catch (e) { toast(e.message); }
}
async function exitRequest() {
  try { await api.post(`/api/sessions/${sess.code}/exit`, {}, headers()); toast('Ждём согласия всех игроков на телефонах', 'info'); }
  catch (e) { toast(e.message); }
}

// ---------------------------------------------------------- оверлеи
function clearTimers() { timers.forEach(clearTimeout); timers = []; }
function hideOverlay() { clearTimers(); overlay.classList.add('hidden'); overlay.dataset.kind = ''; clear(overlay); }

function playCutscene(cs) {
  clearTimers(); clear(overlay);
  overlay.dataset.kind = 'cutscene'; overlay.classList.remove('hidden');
  const sub = h('div', { class: 'sub', 'aria-live': 'assertive' });
  const backdrop = cs.video_url ? h('video', { class: 'bg', src: cs.video_url, autoplay: true, muted: true, loop: true, playsinline: true })
    : cs.still_url ? h('img', { class: 'bg', src: cs.still_url, alt: '' }) : null;
  if (backdrop && cs.video_url) backdrop.muted = true;   // голос диктора идёт отдельной дорожкой
  overlay.append(backdrop, h('div', { class: 'letter t' }), h('div', { class: 'letter b' }),
    h('div', { class: 'fg' }, h('div', { class: 'muted', text: cs.title }), sub,
      h('div', { class: 'muted small', text: 'Пропустить: большинство игроков нажимает «Пропустить» на телефоне' })));
  for (const line of cs.subtitles) timers.push(setTimeout(() => { sub.textContent = line.text; }, line.time * 1000));
  if (cs.audio_url && soundOn) { const a = new Audio(cs.audio_url); a.play().catch(() => toast('Нажмите на экран, чтобы включить звук', 'info')); }
  timers.push(setTimeout(hideOverlay, (cs.duration + 2.5) * 1000));
}

function showDice(r) {
  if (overlay.dataset.kind === 'cutscene') return;
  clearTimers(); clear(overlay); overlay.dataset.kind = 'dice'; overlay.classList.remove('hidden');
  const num = h('div', { class: 'num', text: '…' });
  const box = h('div', { class: 'dice spin' }, h('div', { text: `${r.hero_name} · ${r.label}` }), num,
    h('div', { class: 'muted', id: 'dice-detail', text: '' }));
  overlay.append(box);
  let i = 0;
  const spin = setInterval(() => { num.textContent = String(((i++ * 7) % 20) + 1); }, 70);
  timers.push(setTimeout(() => {
    clearInterval(spin); box.classList.remove('spin'); num.textContent = String(r.natural);
    box.querySelector('#dice-detail').textContent = `${r.natural} ${r.modifier >= 0 ? '+' : '−'} ${Math.abs(r.modifier)} против ${r.dc}: ${OUTCOMES[r.outcome] || r.outcome}`;
  }, 1100));
  timers.push(setTimeout(hideOverlay, 3600));
}

function showPause() {
  clearTimers(); clear(overlay); overlay.dataset.kind = 'pause'; overlay.classList.remove('hidden');
  overlay.append(h('div', { class: 'card stack' }, h('h2', { text: 'Сага на паузе' }),
    h('p', { class: 'muted', text: 'Состояние сохранено. Игроки вернутся на своих героев, когда снова откроют телефоны.' }),
    h('button', { class: 'primary', id: 'btn-resume', text: 'Продолжить', onclick: () => resume(sess.code) }),
    h('button', { class: 'ghost', text: 'В главное меню', onclick: () => { store.del(KEY); sess = null; hideOverlay(); showStart(); } })));
}

boot();
