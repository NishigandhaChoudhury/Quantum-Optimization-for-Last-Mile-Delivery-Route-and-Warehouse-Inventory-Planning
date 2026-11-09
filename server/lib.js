const W = ['A', 'B', 'C'];
const MAX_KM = 25;
const SOLVER_URL = process.env.SOLVER_URL || 'http://127.0.0.1:8001';

const httpError = (status, message) => Object.assign(new Error(message), { status });
const wrap = (fn) => (req, res) => fn(req, res).catch((e) => {
  if (!e.status) console.error(e);
  res.status(e.status || 500).json({ detail: e.status ? e.message : 'Server error: ' + e.message });
});

function haversine(lat1, lon1, lat2, lon2) {
  const r = (x) => (x * Math.PI) / 180;
  const h = Math.sin(r(lat2 - lat1) / 2) ** 2 + Math.cos(r(lat1)) * Math.cos(r(lat2)) * Math.sin(r(lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}
const daysLeft = (expiry) => Math.ceil((new Date(expiry).getTime() - Date.now()) / 86400000);
const stockForSolver = (stock) => stock
  .map((s) => ({ wid: s.wid, product: s.product, units: s.units, days: daysLeft(s.expiryDate) }))
  .filter((s) => s.days > 0);
const orderForSolver = (o) => ({ id: o.orderId, product: o.product, min_shelf: o.minShelfDays,
  dist: { A: o.dist.A, B: o.dist.B, C: o.dist.C }, lat: o.lat, lon: o.lon, category: o.category });

async function solver(path, body, method = 'POST') {
  let res;
  try {
    res = await fetch(SOLVER_URL + path, { method, headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined });
  } catch (e) {
    throw httpError(502, 'The Python solver is not running. Start it with: python solver/solver_app.py');
  }
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw httpError(res.status === 422 ? 400 : res.status, typeof j.detail === 'string' ? j.detail : 'Solver rejected the request.');
  return j;
}

module.exports = { W, MAX_KM, httpError, wrap, haversine, daysLeft, stockForSolver, orderForSolver, solver };
