// Тонкая обёртка над REST. Ошибки сервера приходят как {error:{code,message}}.
export class ApiError extends Error {
  constructor(status, code, message) { super(message); this.status = status; this.code = code; }
}
async function call(method, path, { body, headers } = {}) {
  const res = await fetch(path, {
    method, headers: { ...(body ? { 'Content-Type': 'application/json' } : {}), ...(headers || {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* пустой ответ */ }
  if (!res.ok) {
    const e = data && data.error;
    if (e) throw new ApiError(res.status, e.code, e.message);
    // ошибки валидации FastAPI (422) приходят как {detail:[...]}
    const msg = data && data.detail ? 'Проверьте введённые данные' : `Ошибка ${res.status}`;
    throw new ApiError(res.status, 'http_' + res.status, msg);
  }
  return data;
}
export const api = {
  get: (p, headers) => call('GET', p, { headers }),
  post: (p, body, headers) => call('POST', p, { body: body || {}, headers }),
  stories: () => api.get('/api/stories'),
  heroes: () => api.get('/api/heroes'),
  resumable: () => api.get('/api/sessions/resumable'),
  tableMap: (code, token) => api.get(`/api/maps/${code}/table`, { 'X-Table-Token': token }),
  handMap: (code, token) => api.get(`/api/maps/${code}/hand?device_token=${encodeURIComponent(token)}`),
};
export const store = {
  get(key) { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* приватный режим */ } },
  del(key) { try { localStorage.removeItem(key); } catch { /* ignore */ } },
};
