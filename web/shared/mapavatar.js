// Токен героя на карте: круг с монограммой и картинкой, если файл есть.
import { s } from './dom.js';
function hue(id) { let n = 0; for (const c of id) n = (n * 31 + c.charCodeAt(0)) % 360; return n; }
export function avatarSvg(token, x, y) {
  const hh = hue(token.hero_id);
  const g = s('g', { class: 'token', transform: `translate(${x},${y})`, 'data-hero': token.hero_id });
  g.append(s('circle', { r: 17, fill: `hsl(${hh} 35% 24%)`, style: token.wounded ? 'stroke:#e0545c' : '' }));
  g.append(s('text', { y: 5, 'font-size': 15, 'font-family': 'Georgia,serif' }, (token.name || token.hero_id)[0].toUpperCase()));
  g.append(s('title', {}, token.name || token.hero_id));
  const img = s('image', { href: `/assets/heroes/${token.hero_id}.webp`, x: -17, y: -17, width: 34, height: 34, 'clip-path': 'circle(17px at 17px 17px)' });
  img.addEventListener('error', () => img.remove());
  g.append(img);
  return g;
}
