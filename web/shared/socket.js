// WebSocket с переподключением, ping и повтором пропущенных событий по seq.
export class Socket {
  constructor(path, { onMessage, onStatus }) {
    this.path = path; this.onMessage = onMessage; this.onStatus = onStatus || (() => {});
    this.lastSeq = 0; this.closed = false; this.retry = 0; this.ws = null; this.timer = null;
  }
  connect() {
    if (this.closed) return;
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const sep = this.path.includes('?') ? '&' : '?';
    this.ws = new WebSocket(`${proto}://${location.host}${this.path}${sep}last_seq=${this.lastSeq}`);
    this.ws.onopen = () => { this.retry = 0; this.onStatus(true); this.ping = setInterval(() => this.send('ping'), 20000); };
    this.ws.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.seq && msg.seq > this.lastSeq && msg.type !== 'hero.state' && msg.type !== 'table.state') this.lastSeq = msg.seq;
      this.onMessage(msg);
    };
    this.ws.onclose = (ev) => {
      clearInterval(this.ping); this.onStatus(false, ev.code);
      if (this.closed || ev.code === 4401) return;       // 4401: токен недействителен, повторять бессмысленно
      const delay = Math.min(8000, 500 * 2 ** this.retry++);
      this.timer = setTimeout(() => this.connect(), delay);
    };
  }
  send(type, payload = {}) {
    if (this.ws && this.ws.readyState === 1) { this.ws.send(JSON.stringify({ type, payload })); return true; }
    return false;
  }
  close() { this.closed = true; clearTimeout(this.timer); clearInterval(this.ping); if (this.ws) this.ws.close(); }
}
