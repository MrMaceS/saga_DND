// Мини-помощники для DOM без зависимостей.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'text') el.textContent = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'dataset') Object.assign(el.dataset, v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}
export const svgNS = 'http://www.w3.org/2000/svg';
export function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(svgNS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== null && v !== undefined) el.setAttribute(k, v);
  for (const c of children.flat()) if (c) el.append(c.nodeType ? c : document.createTextNode(String(c)));
  return el;
}
export function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
export function toast(message, kind = 'error', ms = 4500) {
  let zone = document.querySelector('.toast-zone');
  if (!zone) { zone = h('div', { class: 'toast-zone', role: 'status', 'aria-live': 'polite' }); document.body.append(zone); }
  const t = h('div', { class: `toast ${kind === 'error' ? '' : 'info'}`, text: message });
  zone.append(t);
  setTimeout(() => t.remove(), ms);
}
export function cells(total, used) {
  return h('span', { class: 'cells', title: `Стойкость ${total - used} из ${total}` },
    Array.from({ length: total }, (_, i) => h('span', { class: 'cell' + (i < used ? ' used' : '') })));
}
export const STAT_NAMES = { strength: 'Сила', agility: 'Ловкость', wits: 'Разум', spirit: 'Дух' };
export const OUTCOMES = {
  critical_fail: 'Критический провал', fail_with_consequence: 'Провал с последствием', fail: 'Провал',
  minimal_success: 'Минимальный успех', success: 'Успех', great_success: 'Большой успех',
};
