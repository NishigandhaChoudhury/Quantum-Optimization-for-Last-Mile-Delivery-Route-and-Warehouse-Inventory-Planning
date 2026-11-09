export const getToken = () => localStorage.getItem('token');
export async function api(path, { method, body } = {}) {
  const r = await fetch('/api' + path, {
    method: method || (body ? 'POST' : 'GET'),
    headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: 'Bearer ' + getToken() } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (r.status === 401 && getToken()) { localStorage.removeItem('token'); window.dispatchEvent(new Event('logout')); }
  if (!r.ok) throw new Error(j.detail || 'Request failed');
  return j;
}
