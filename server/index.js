require('dotenv').config();
const mongoose = require('mongoose');
const app = require('./app');
const { Warehouse } = require('./models');
const { seedAll } = require('./seed');

const PORT = process.env.PORT || 4000;
const URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/expiry_planner';

mongoose.connect(URI, { serverSelectionTimeoutMS: 6000 }).then(async () => {
  console.log('MongoDB connected');
  if ((await Warehouse.countDocuments({})) === 0) {
    try { console.log('Empty database, seeding from server/data ...', await seedAll()); }
    catch (e) { console.error('Seed skipped:', e.message); }
  }
  app.listen(PORT, () => console.log(`API on http://127.0.0.1:${PORT}`));
}).catch((e) => {
  console.error('Cannot connect to MongoDB at', URI, '\n', e.message,
    '\nInstall and start MongoDB, or put a MongoDB Atlas URI in server/.env (MONGO_URI).');
  process.exit(1);
});
