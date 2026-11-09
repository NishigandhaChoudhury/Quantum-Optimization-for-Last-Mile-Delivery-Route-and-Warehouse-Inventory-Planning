const mongoose = require('mongoose');
const { Schema } = mongoose;

const User = mongoose.model('User', new Schema({
  email: { type: String, unique: true }, name: String,
  role: { type: String, enum: ['admin', 'planner'], default: 'planner' }, passwordHash: String,
}));
const Warehouse = mongoose.model('Warehouse', new Schema({ wid: String, lat: Number, lon: Number }));
const Stock = mongoose.model('Stock', new Schema({
  wid: String, product: String, units: Number, expiryDate: Date,
}));
const Order = mongoose.model('Order', new Schema({
  orderId: { type: String, unique: true }, product: String, category: String, lat: Number, lon: Number,
  dist: { A: Number, B: Number, C: Number }, minShelfDays: Number,
  status: { type: String, default: 'pending' },          // pending | dispatched
  source: { type: String, default: 'dataset' },          // dataset | manual
  assignedWid: String, method: String, kmShipped: Number, kmNearest: Number,
  daysLeftShipped: Number, dispatchedAt: Date,
}));
const Bench = mongoose.model('Bench', new Schema({
  createdAt: { type: Date, default: Date.now }, params: Schema.Types.Mixed,
  result: Schema.Types.Mixed, stockSnapshot: Schema.Types.Mixed,
}));

module.exports = { User, Warehouse, Stock, Order, Bench };
