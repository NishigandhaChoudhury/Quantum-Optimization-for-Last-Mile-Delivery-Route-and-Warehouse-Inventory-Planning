const express = require('express'), cors = require('cors'), path = require('path'), fs = require('fs');
const bcrypt = require('bcryptjs'), jwt = require('jsonwebtoken');
const { User, Warehouse, Stock, Order, Bench } = require('./models');
const L = require('./lib');
const { W, MAX_KM, httpError, wrap, haversine, daysLeft, stockForSolver, orderForSolver, solver } = L;

const SECRET = () => process.env.JWT_SECRET || 'dev_secret';
const app = express();
app.use(cors()); app.use(express.json({ limit: '10mb' }));
const api = express.Router();

/* ---------- auth ---------- */
const auth = (req, res, next) => {
  try {
    const t = (req.headers.authorization || '').replace('Bearer ', '');
    req.user = jwt.verify(t, SECRET()); next();
  } catch { res.status(401).json({ detail: 'Please sign in.' }); }
};
const admin = (req, res, next) => req.user.role === 'admin' ? next() : res.status(403).json({ detail: 'Admin only.' });

api.post('/auth/login', wrap(async (req, res) => {
  const { email, password } = req.body || {};
  const u = await User.findOne({ email: String(email || '').toLowerCase() }).lean();
  if (!u || !bcrypt.compareSync(String(password || ''), u.passwordHash)) throw httpError(401, 'Wrong email or password.');
  const user = { id: String(u._id), email: u.email, name: u.name, role: u.role };
  res.json({ token: jwt.sign(user, SECRET(), { expiresIn: '12h' }), user });
}));
api.get('/auth/me', auth, (req, res) => res.json({ user: req.user }));

/* ---------- overview, stock, orders ---------- */
const stockView = (s) => ({ id: String(s._id), wid: s.wid, product: s.product, units: s.units,
  expiryDate: s.expiryDate, daysLeft: daysLeft(s.expiryDate) });

api.get('/overview', auth, wrap(async (req, res) => {
  const [warehouses, stock, pending, dispatched, drops] = await Promise.all([
    Warehouse.find({}).lean(), Stock.find({}).lean(), Order.countDocuments({ status: 'pending' }),
    Order.find({ status: 'dispatched' }).lean(), Order.find({}).limit(300).lean()]);
  const sv = stock.map(stockView);
  const km = dispatched.reduce((a, o) => a + (o.kmShipped || 0), 0);
  const kmN = dispatched.reduce((a, o) => a + (o.kmNearest || 0), 0);
  res.json({
    warehouses: warehouses.map((w) => ({ wid: w.wid, lat: w.lat, lon: w.lon })),
    drops: drops.map((o) => ({ lat: o.lat, lon: o.lon })),
    stock: sv.sort((a, b) => a.product.localeCompare(b.product) || a.wid.localeCompare(b.wid)),
    counts: { pending, dispatched: dispatched.length, units: sv.reduce((a, s) => a + s.units, 0),
      expiringSoon: sv.filter((s) => s.daysLeft > 0 && s.daysLeft <= 30).reduce((a, s) => a + s.units, 0) },
    impact: { orders: dispatched.length, km, kmNearest: kmN,
      avgDaysLeft: dispatched.length ? dispatched.reduce((a, o) => a + (o.daysLeftShipped || 0), 0) / dispatched.length : null },
  });
}));

api.get('/stock', auth, wrap(async (req, res) => {
  const s = await Stock.find({}).lean();
  res.json({ items: s.map(stockView).sort((a, b) => a.product.localeCompare(b.product) || a.wid.localeCompare(b.wid)) });
}));
api.put('/stock/:id', auth, admin, wrap(async (req, res) => {
  const set = {};
  if (req.body.units !== undefined) {
    const u = Number(req.body.units);
    if (!Number.isInteger(u) || u < 0) throw httpError(400, 'Units must be a whole number, 0 or more.');
    set.units = u;
  }
  if (req.body.expiryDate) {
    const d = new Date(req.body.expiryDate);
    if (isNaN(d)) throw httpError(400, 'Invalid expiry date.');
    set.expiryDate = d;
  }
  await Stock.updateOne({ _id: req.params.id }, { $set: set });
  res.json({ ok: true });
}));

api.get('/orders', auth, wrap(async (req, res) => {
  const f = req.query.status ? { status: String(req.query.status) } : {};
  const page = Math.max(1, Number(req.query.page) || 1), limit = Math.min(100, Number(req.query.limit) || 25);
  const [total, items] = await Promise.all([Order.countDocuments(f),
    Order.find(f).sort({ _id: 1 }).skip((page - 1) * limit).limit(limit).lean()]);
  res.json({ total, page, limit, items: items.map((o) => ({ ...o, _id: String(o._id) })) });
}));
api.get('/products', auth, wrap(async (req, res) => {
  const s = await Stock.find({}).lean(); res.json({ products: [...new Set(s.map((x) => x.product))].sort() });
}));
api.post('/orders', auth, wrap(async (req, res) => {
  const { product, lat, lon, minShelfDays } = req.body || {};
  const la = Number(lat), lo = Number(lon), ms = Number(minShelfDays);
  if (!product || !isFinite(la) || !isFinite(lo) || !isFinite(ms) || ms < 0) throw httpError(400, 'Enter a product, a drop location (lat and lon) and the minimum shelf life in days.');
  const wh = await Warehouse.find({}).lean();
  if (wh.length < 3) throw httpError(400, 'Warehouses are not set up. Run the seed first.');
  const dist = {}; wh.forEach((w) => { dist[w.wid] = Math.round(haversine(w.lat, w.lon, la, lo) * 100) / 100; });
  const o = await Order.create({ orderId: 'NEW-' + Date.now().toString(36), product, category: 'Manual', lat: la, lon: lo,
    dist, minShelfDays: ms, status: 'pending', source: 'manual' });
  res.json({ orderId: o.orderId, dist });
}));

/* ---------- planner and dispatch ---------- */
api.post('/plan', auth, wrap(async (req, res) => {
  const ids = (req.body || {}).orderIds || [];
  if (!Array.isArray(ids) || ids.length < 1 || ids.length > 4) throw httpError(400, 'Choose 1 to 4 pending orders.');
  const orders = [];
  for (const id of ids) {
    const o = await Order.findOne({ orderId: id }).lean();
    if (!o || o.status !== 'pending') throw httpError(400, `Order ${id} is not pending.`);
    orders.push(o);
  }
  const stock = await Stock.find({}).lean();
  const out = await solver('/plan', { orders: orders.map(orderForSolver), stock: stockForSolver(stock),
    alpha_greedy: Number(req.body.alphaGreedy ?? 2), alpha_joint: Number(req.body.alphaJoint ?? 1) });
  res.json({ ...out, orders: orders.map((o) => ({ orderId: o.orderId, product: o.product, minShelfDays: o.minShelfDays, dist: o.dist })) });
}));

api.post('/dispatch', auth, wrap(async (req, res) => {
  const { orderIds, plan, method } = req.body || {};
  if (!Array.isArray(orderIds) || !Array.isArray(plan) || orderIds.length !== plan.length || orderIds.length < 1 || orderIds.length > 4)
    throw httpError(400, 'Invalid dispatch request.');
  const orders = [];
  for (const id of orderIds) {
    const o = await Order.findOne({ orderId: id }).lean();
    if (!o || o.status !== 'pending') throw httpError(409, `Order ${id} is no longer pending.`);
    orders.push(o);
  }
  const taken = [], results = [];
  try {
    for (let i = 0; i < orders.length; i++) {
      const o = orders[i], w = plan[i];
      if (!w) { results.push({ orderId: o.orderId, assignedWid: null }); continue; }
      if (!W.includes(w)) throw httpError(400, 'Unknown warehouse ' + w);
      if (o.dist[w] > MAX_KM) throw httpError(409, `Order ${o.orderId} is beyond the ${MAX_KM} km limit from warehouse ${w}.`);
      const stocks = await Stock.find({ product: o.product }).lean();
      const feasible = stocks.filter((s) => s.units > 0 && daysLeft(s.expiryDate) >= o.minShelfDays && o.dist[s.wid] <= MAX_KM);
      const s = feasible.find((x) => x.wid === w);
      if (!s) throw httpError(409, `Warehouse ${w} cannot supply ${o.product} for ${o.orderId} (no stock, or shelf life too short). Plan again.`);
      const upd = await Stock.findOneAndUpdate({ _id: s._id, units: { $gt: 0 } }, { $inc: { units: -1 } }, { new: true });
      if (!upd) throw httpError(409, 'Stock changed while dispatching. Plan again.');
      taken.push(s._id);
      results.push({ orderId: o.orderId, assignedWid: w, kmShipped: o.dist[w],
        kmNearest: Math.min(...feasible.map((f) => o.dist[f.wid])), daysLeftShipped: daysLeft(s.expiryDate) });
    }
  } catch (e) {
    for (const id of taken) await Stock.updateOne({ _id: id }, { $inc: { units: 1 } });
    throw e;
  }
  for (const r of results) if (r.assignedWid)
    await Order.updateOne({ orderId: r.orderId }, { $set: { status: 'dispatched', assignedWid: r.assignedWid,
      method: String(method || 'manual'), kmShipped: r.kmShipped, kmNearest: r.kmNearest,
      daysLeftShipped: r.daysLeftShipped, dispatchedAt: new Date() } });
  res.json({ dispatched: results.filter((r) => r.assignedWid).length, unserved: results.filter((r) => !r.assignedWid).length, results });
}));

/* ---------- benchmark and quantum (Python solver) ---------- */
const jobMeta = {};
const poolAndStock = async () => {
  const [orders, stock] = await Promise.all([Order.find({}).lean(), Stock.find({}).lean()]);
  return { pool: orders.map(orderForSolver), stock: stockForSolver(stock) };
};

api.post('/benchmark', auth, wrap(async (req, res) => {
  const b = req.body || {};
  const params = { per_day: Number(b.per_day) || 12, runs: Number(b.runs) || 5, alpha_greedy: Number(b.alpha_greedy ?? 2),
    alpha_joint: Number(b.alpha_joint ?? 1), alpha_quantum: 1.0, include_quantum: !!b.include_quantum, quantum_runs: Number(b.quantum_runs) || 1 };
  const data = await poolAndStock();
  const { job } = await solver('/benchmark', { ...data, ...params });
  jobMeta[job] = { params, stockSnapshot: data.stock, runId: null };
  res.json({ job });
}));
api.get('/job/:id', auth, wrap(async (req, res) => {
  const j = await solver('/job/' + encodeURIComponent(req.params.id), null, 'GET');
  const m = jobMeta[req.params.id];
  if (j.status === 'done' && m && !m.runId) {
    const run = await Bench.create({ params: m.params, result: j.result, stockSnapshot: m.stockSnapshot });
    m.runId = String(run._id);
  }
  res.json({ ...j, runId: m ? m.runId : null });
}));
api.get('/benchmarks', auth, wrap(async (req, res) => {
  const runs = await Bench.find({}).sort({ createdAt: -1 }).limit(20).lean();
  res.json({ items: runs.map((r) => ({ id: String(r._id), createdAt: r.createdAt, params: r.params })) });
}));
api.get('/benchmarks/:id', auth, wrap(async (req, res) => {
  const r = await Bench.findById(req.params.id).lean();
  if (!r) throw httpError(404, 'Run not found.');
  res.json({ id: String(r._id), createdAt: r.createdAt, params: r.params, result: r.result });
}));
api.post('/quantum', auth, wrap(async (req, res) => {
  const data = await poolAndStock();
  res.json(await solver('/quantum', { seed: Number((req.body || {}).seed) || 1, ...data }));
}));

/* ---------- admin ---------- */
api.post('/admin/reseed', auth, admin, wrap(async (req, res) => {
  try { res.json(await require('./seed').seedAll()); } catch (e) { throw httpError(400, e.message); }
}));

app.use('/api', api);
const dist = path.join(__dirname, '..', 'client', 'dist');
if (fs.existsSync(dist)) {
  app.use(express.static(dist));
  app.get(/^\/(?!api).*/, (req, res) => res.sendFile(path.join(dist, 'index.html')));
}
module.exports = app;
