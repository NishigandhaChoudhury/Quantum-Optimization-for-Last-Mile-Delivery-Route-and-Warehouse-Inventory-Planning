# Expiry-aware warehouse planner (MERN + Python solver)

React (client) -> Express/Node (server) -> MongoDB, and Node -> Python FastAPI (solver: classical, QAOA, hybrid).

## Needs
Node 18+, Python 3.10+, MongoDB running locally (or a MongoDB Atlas URI in `server/.env`, key `MONGO_URI`).

## Run (from this folder)
1. Copy `inventory.csv`, `orders_full.csv`, `warehouses.csv` into `server/data`.
2. `npm run setup`   (installs everything, once)
3. `npm run dev`     (starts API :4000, web :5173, solver :8001)
4. Open http://localhost:5173

The first start loads the CSVs into MongoDB automatically (stock units = source stock x 15, expiry = today + remaining days).

## Logins
planner@demo.com / planner123, admin@demo.com / admin123 (admin can edit stock and reload data).

## Pages
Overview, Orders (add orders), Planner (compare methods, then Dispatch updates stock), Stock, Benchmark (saved to MongoDB), Quantum lab.
