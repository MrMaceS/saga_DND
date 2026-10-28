// Динамическая отрисовка карты по зонам и смежности из API. Имена зон показываются только у посещённых.
import { s } from './dom.js';
import { avatarSvg } from './mapavatar.js';

const W = 1000, H = 560, ZW = 150, ZH = 78;

// Если сервер не прислал координаты, раскладываем граф по слоям (поиск в ширину).
export function autoLayout(zones, adjacency, rootId) {
  const ids = zones.map((z) => z.id);
  const root = ids.includes(rootId) ? rootId : ids[0];
  const layer = { [root]: 0 };
  const queue = [root];
  while (queue.length) {
    const cur = queue.shift();
    for (const n of adjacency[cur] || []) if (!(n in layer) && ids.includes(n)) { layer[n] = layer[cur] + 1; queue.push(n); }
  }
  for (const id of ids) if (!(id in layer)) layer[id] = 0;
  const byLayer = {};
  for (const id of ids) (byLayer[layer[id]] = byLayer[layer[id]] || []).push(id);
  const maxLayer = Math.max(...Object.keys(byLayer).map(Number), 1);
  const pos = {};
  for (const [l, list] of Object.entries(byLayer)) {
    list.forEach((id, i) => { pos[id] = [10 + (80 * Number(l)) / maxLayer, ((i + 1) * 100) / (list.length + 1)]; });
  }
  return pos;
}

export function renderMap(svg, map, { currentZone = null, tokens = [], onZoneClick = null, clickable = null } = {}) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('class', 'map');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Карта');
  const zones = map.zones || [];
  const adjacency = map.adjacency || {};
  const auto = autoLayout(zones, adjacency, currentZone || (zones.find((z) => z.visited) || zones[0] || {}).id);
  const pos = {};
  for (const z of zones) {
    const p = z.x != null && z.y != null ? [z.x, z.y] : auto[z.id];
    pos[z.id] = [60 + (p[0] / 100) * (W - 120), 50 + (p[1] / 100) * (H - 100)];
  }
  const drawn = new Set();
  for (const [a, ns] of Object.entries(adjacency)) {
    for (const b of ns) {
      const key = [a, b].sort().join('|');
      if (drawn.has(key) || !pos[a] || !pos[b]) continue;
      drawn.add(key);
      svg.append(s('line', { class: 'edge', x1: pos[a][0], y1: pos[a][1], x2: pos[b][0], y2: pos[b][1] }));
    }
  }
  for (const z of zones) {
    const [x, y] = pos[z.id];
    const known = z.visited || z.name;
    const isClickable = onZoneClick && (clickable ? clickable(z) : true);
    const g = s('g', {
      class: `zone ${known ? 'known' : 'unknown'}${z.id === currentZone ? ' current' : ''}${isClickable ? ' clickable' : ''}`,
      'data-zone': z.id, transform: `translate(${x - ZW / 2},${y - ZH / 2})`,
    });
    g.append(s('rect', { width: ZW, height: ZH, rx: 10 }));
    g.append(s('text', { x: ZW / 2, y: known ? ZH / 2 + 8 : ZH / 2 + 12, 'font-size': known ? 24 : 34 }, known ? z.name : '?'));
    if (isClickable) { g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button'); g.addEventListener('click', () => onZoneClick(z)); g.addEventListener('keydown', (e) => { if (e.key === 'Enter') onZoneClick(z); }); }
    svg.append(g);
  }
  // токены героев; в зоне 4 и больше героев показываем одну стопку «×N»
  const byZone = {};
  for (const t of tokens) (byZone[t.zone_id] = byZone[t.zone_id] || []).push(t);
  for (const [zoneId, list] of Object.entries(byZone)) {
    if (!pos[zoneId]) continue;
    const [x, y] = pos[zoneId];
    if (list.length >= 4) {
      const g = s('g', { class: 'token stack', transform: `translate(${x},${y + ZH / 2 + 4})` },
        s('circle', { r: 17, fill: '#3a2a2a' }), s('text', { y: 5 }, `×${list.length}`));
      svg.append(g);
      continue;
    }
    list.forEach((t, i) => {
      const dx = (i - (list.length - 1) / 2) * 40;
      svg.append(avatarSvg(t, x + dx, y + ZH / 2 + 4));
    });
  }
  return svg;
}
