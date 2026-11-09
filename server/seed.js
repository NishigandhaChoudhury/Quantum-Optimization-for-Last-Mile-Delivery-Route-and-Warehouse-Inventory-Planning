// Loads your three CSVs (server/data) into MongoDB. Run:  npm run seed
const fs = require('fs'), path = require('path');
const { parse } = require('csv-parse/sync');
const bcrypt = require('bcryptjs');

const DATA = path.join(__dirname, 'data');
const read = (f) => {
  const p = path.join(DATA, f);
  if (!fs.existsSync(p)) throw new Error(`Missing ${f}. Copy inventory.csv, orders_full.csv and warehouses.csv into server/data.`);
  return parse(fs.readFileSync(p), { columns: true, skip_empty_lines: true, cast: true });
};

async function seedAll() {
  const { User, Warehouse, Stock, Order } = require('./models');
  const scale = Number(process.env.STOCK_SCALE || 15);
  const wh = read('warehouses.csv'), inv = read('inventory.csv'), ord = read('orders_full.csv');
  const need = (rows, cols, f) => cols.forEach((c) => { if (!(c in rows[0])) throw new Error(`${f} is missing column ${c}`); });
  need(inv, ['wid', 'Product_Name', 'stock', 'remaining_days'], 'inventory.csv');
  need(ord, ['Order_ID', 'Category', 'Drop_Latitude', 'Drop_Longitude', 'dist_A', 'dist_B', 'dist_C', 'product', 'min_shelf_days'], 'orders_full.csv');
  need(wh, ['wid', 'lat', 'lon'], 'warehouses.csv');

  await Promise.all([Warehouse.deleteMany({}), Stock.deleteMany({}), Order.deleteMany({})]);
  await Warehouse.insertMany(wh.map((r) => ({ wid: String(r.wid), lat: r.lat, lon: r.lon })));
  const day = 86400000, now = Date.now();
  await Stock.insertMany(inv.map((r) => ({ wid: String(r.wid), product: String(r.Product_Name),
    units: Math.round(r.stock * scale), expiryDate: new Date(now + r.remaining_days * day) })));
  await Order.insertMany(ord.map((r) => ({ orderId: String(r.Order_ID), product: String(r.product), category: String(r.Category),
    lat: r.Drop_Latitude, lon: r.Drop_Longitude, dist: { A: r.dist_A, B: r.dist_B, C: r.dist_C },
    minShelfDays: r.min_shelf_days, status: 'pending', source: 'dataset' })));

  for (const u of [{ email: 'admin@demo.com', name: 'Admin', role: 'admin', pw: 'admin123' },
                   { email: 'planner@demo.com', name: 'Planner', role: 'planner', pw: 'planner123' }]) {
    if (!(await User.findOne({ email: u.email }).lean()))
      await User.create({ email: u.email, name: u.name, role: u.role, passwordHash: bcrypt.hashSync(u.pw, 8) });
  }
  return { warehouses: wh.length, stock: inv.length, orders: ord.length };
}

module.exports = { seedAll };

if (require.main === module) {
  require('dotenv').config();
  const mongoose = require('mongoose');
  mongoose.connect(process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/expiry_planner')
    .then(seedAll).then((r) => { console.log('Seeded:', r); process.exit(0); })
    .catch((e) => { console.error(e.message); process.exit(1); });
}
