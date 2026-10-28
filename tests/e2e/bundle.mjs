// jsdom не умеет ES-модули, поэтому для проверки склеиваем модули страницы в один классический скрипт.
import fs from 'node:fs';
import path from 'node:path';

const WEB = path.resolve(path.dirname(new URL(import.meta.url).pathname), '../../web');
const ORDER = {
  table: ['shared/dom.js', 'shared/api.js', 'shared/socket.js', 'shared/mapavatar.js', 'shared/avatar.js', 'shared/map.js', 'shared/clocks.js', 'table/table.js'],
  hand: ['shared/dom.js', 'shared/api.js', 'shared/socket.js', 'shared/mapavatar.js', 'shared/avatar.js', 'shared/map.js', 'hand/hand.js'],
};
export function bundle(page) {
  return ORDER[page].map((f) => {
    let src = fs.readFileSync(path.join(WEB, f), 'utf8');
    src = src.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm, '');
    src = src.replace(/^export\s+(async\s+function|function|class|const|let)\s/gm, '$1 ');
    return `// ---- ${f}\n${src}`;
  }).join('\n');
}
