// Часы угроз: безымянное кольцо с тремя стадиями (намёк) или часы с названием и делениями (разведано).
import { h, s } from './dom.js';

const R = 30, C = 2 * Math.PI * R;
const STAGE = { quiet: ['тихо', 0.34], uneasy: ['тревожно', 0.67], near_doom: ['близко к беде', 1] };
const ICON = { knock: '◉', anchor: '⚓', shadows: '☾' };

export function clockEl(c) {
  const svg = s('svg', { viewBox: '0 0 76 76', role: 'img', 'aria-label': c.named ? `${c.name}: ${c.filled} из ${c.segments}` : 'Неизвестная угроза' });
  const ring = (attrs) => s('circle', { cx: 38, cy: 38, r: R, fill: 'none', 'stroke-width': 9, transform: 'rotate(-90 38 38)', ...attrs });
  let stage;
  if (c.named && c.segments) {
    const gap = 6, seg = C / c.segments - gap;
    svg.append(ring({ stroke: '#3a3f4a', 'stroke-dasharray': `${seg} ${gap}` }));
    if (c.filled > 0) svg.append(ring({ stroke: '#e0545c', 'stroke-dasharray': Array(c.filled).fill(`${seg} ${gap}`).join(' ') + ` 0 ${C}` }));
    svg.append(s('text', { x: 38, y: 44, 'text-anchor': 'middle', 'font-size': 18, fill: '#e9e2d0', 'font-family': 'Georgia,serif' }, `${c.filled}/${c.segments}`));
    stage = `${c.filled} из ${c.segments}`;
  } else {
    const [label, frac] = STAGE[c.stage] || STAGE.quiet;
    svg.append(ring({ stroke: '#3a3f4a' }));
    svg.append(ring({ stroke: '#d0a94b', 'stroke-dasharray': `${C * frac} ${C}`, 'stroke-linecap': 'round' }));
    svg.append(s('text', { x: 38, y: 47, 'text-anchor': 'middle', 'font-size': 26, fill: '#9a9484', 'font-family': 'Georgia,serif' }, '?'));
    stage = label;
  }
  return h('div', { class: 'clock', 'data-clock': c.id },
    svg,
    h('div', { class: 'name', text: c.named ? `${ICON[c.icon] || ''} ${c.name}` : (ICON[c.icon] || '·') }),
    h('div', { class: 'stage', text: stage }));
}
