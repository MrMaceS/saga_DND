// Аватарка героя: картинка из assets/heroes/{id}.webp, а если файла ещё нет, нарисованная монограмма.
import { h, s } from './dom.js';

function hue(id) { let n = 0; for (const c of id) n = (n * 31 + c.charCodeAt(0)) % 360; return n; }

export function monogram(heroId, name, size) {
  const letter = (name || heroId || '?').trim()[0].toUpperCase();
  const hh = hue(heroId || name || '');
  return s('svg', { width: size, height: size, viewBox: '0 0 40 40', class: 'avatar', role: 'img', 'aria-label': name || heroId },
    s('circle', { cx: 20, cy: 20, r: 19, fill: `hsl(${hh} 35% 22%)`, stroke: `hsl(${hh} 40% 55%)`, 'stroke-width': 2 }),
    s('text', { x: 20, y: 26, 'text-anchor': 'middle', 'font-size': 18, 'font-family': 'Georgia,serif', fill: `hsl(${hh} 40% 85%)` }, letter));
}

export function avatar(heroId, name, size = 40) {
  const holder = h('span', { style: `display:inline-flex;width:${size}px;height:${size}px;flex:none`, title: name || heroId });
  const img = h('img', { class: 'avatar', width: size, height: size, alt: name || heroId, src: `/assets/heroes/${heroId}.webp` });
  img.addEventListener('error', () => { holder.replaceChildren(monogram(heroId, name, size)); }, { once: true });
  holder.append(img);
  return holder;
}
