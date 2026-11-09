# Expiry-Aware Warehouse Planner

Quantum Optimization for Last-Mile Delivery Route and Warehouse Inventory Planning
Capstone ASAC-CP-006 (CSE-AIML), Alliance School of Advanced Computing

**Live demo:** https://quantum-optimization-for-last-mile-6r1l.onrender.com

Hosted on Render's free plan, so the first load can take about a minute to wake up. Demo logins are in the "Run locally" section below.

## Problem

Perishable orders can be shipped from any of 3 warehouses. Shipping from the nearest one keeps trips short but lets stock expire. This app decides which warehouse ships each order, using stock expiry and distance, and compares several methods on the same orders.

## Methods compared

| Method | Idea |
|---|---|
| Nearest warehouse | Today's practice (baseline) |
| FEFO | Filter warehouses with stock, drop those beyond the distance limit, pick the earliest expiry |
| Cost-aware greedy | Greedy choice balancing distance and expiry |
| Joint exact | Solves a batch of orders together, so they compete for limited stock |
| QAOA (simulated) | 12-qubit circuit for a batch of 4 orders x 3 warehouses |
| QAOA + repair + refine | Hybrid: repair invalid samples, then refine |

## Data (semi-synthetic)

- **Real:** 440 perishable orders around Jaipur from the Amazon Delivery dataset (43,739 rows); 3 warehouses found by KMeans on real store points; real haversine distances; products, stock and expiry dates from the Kaggle Grocery Inventory dataset (991 rows).
- **Synthetic (seeded, reproducible):** which warehouse holds each stock batch, which product each order asks for, minimum shelf life (7/14/30 days), and stock scaling.

No public dataset links orders to warehouse stock, so this part is generated. Results show how the methods behave under these assumptions, not the performance of a real company.

## Results

30-day replay, 5 random runs each, starting from the same stock.

**360 orders**

| Method | Units expired | Unserved orders | Total cost vs nearest |
|---|---|---|---|
| Nearest warehouse | 83.6 | 62.2 | baseline |
| FEFO | 49.6 | 15.0 | -10.8% |
| Cost-aware greedy | 49.6 | 14.8 | -10.9% |
| Joint exact | 65.0 | 14.8 | -9.6% |

**720 orders**

| Method | Units expired | Unserved orders | Total cost vs nearest |
|---|---|---|---|
| Nearest warehouse | 75.4 | 304.2 | baseline |
| FEFO / Cost-aware greedy | 14.6 | 229.6 | -9.0% |
| Joint exact | 32.2 | 247.0 | -6.6% |

**Quantum (360 orders, 1 run):** QAOA only changed cost by -0.6% (worse than nearest); QAOA + repair + refine reached 10.4% lower cost, against 11.9% for FEFO.

**Conclusion:** expiry-aware assignment beat the nearest-warehouse rule in 5 of 5 runs at both demand levels, at about 2 km more per order. A simple FEFO rule performs as well as the joint solver. The quantum methods add no gain at this size, and we make no claim of quantum advantage.

## Tech stack

- **Frontend:** React (Vite)
- **Backend:** Node.js, Express, JWT login with admin and planner roles
- **Database:** MongoDB (local or Atlas)
- **Solver service:** Python (FastAPI) with a numpy QAOA simulator

## Features

- Login with admin and planner roles
- Add orders by drop location; distances to each warehouse are calculated
- Planner compares methods; Dispatch deducts stock in the database and rolls back if any order in the batch fails
- Overview shows km driven by your dispatches against shipping from the nearest warehouse
- Benchmark runs are saved in MongoDB
- Stock page, editable by admin
- Quantum lab compares QAOA with the exact answer on one batch

## Project structure

```
client/    React app
server/    Express API, MongoDB models, seed script, data/ (CSV files)
solver/    Python solver service (engine.py, solver_app.py)
```

## Run locally

**Requirements:** Node 18+, Python 3.10+, and a MongoDB database (local, or a free MongoDB Atlas cluster).

1. Clone the repo and open the folder.
2. Copy `server/.env.example` to `server/.env` and fill it in:
   ```
   PORT=4000
   MONGO_URI=mongodb+srv://USERNAME:PASSWORD@YOUR_CLUSTER.mongodb.net/expiry_planner
   JWT_SECRET=change_this_secret
   SOLVER_URL=http://127.0.0.1:8001
   STOCK_SCALE=15
   ```
3. Make sure `inventory.csv`, `orders_full.csv` and `warehouses.csv` are in `server/data`.
4. Install everything (once):
   ```
   npm run setup
   ```
5. Start all three services:
   ```
   npm run dev
   ```
6. Open `http://localhost:5173`.

**Demo logins**

| Role | Email | Password |
|---|---|---|
| Planner | planner@demo.com | planner123 |
| Admin | admin@demo.com | admin123 |

These are demo accounts for local use only.

## Notes

- The first start loads the CSVs into MongoDB automatically.
- Stock in MongoDB is the source inventory x 15 (`STOCK_SCALE`). Expiry is the first load date plus the remaining days, so "days left" counts down from that day.
- Benchmark runs start from the current stock, so they change as you dispatch. On the Stock page (admin), **Reload data from CSV files** resets everything.
- Never commit `server/.env`. It is listed in `.gitignore`.

## Limitations

- Data is semi-synthetic.
- Cost weights are assumptions: an unserved order costs 30 km-equivalent and an expired unit 15 km-equivalent.
- Distances are direct (not full routes), stock is not replenished during the replay, and there are 5 products.
- The quantum result comes from a simulator and a single run, not real hardware.

## Future work

Demand forecasting, full route planning, real quantum hardware runs, restocking, and deployment.
