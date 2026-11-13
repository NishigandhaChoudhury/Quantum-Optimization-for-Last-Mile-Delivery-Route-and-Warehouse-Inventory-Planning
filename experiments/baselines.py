# baselines.py
import itertools, json
import numpy as np, pandas as pd

rng = np.random.default_rng(42)
ALPHA, MAX_KM, N_BATCH, B = 0.1, 20, 200, 4   # expiry weight, distance limit, batches, orders/batch
W = ["A", "B", "C"]

inv = pd.read_csv("inventory.csv")
orders = pd.read_csv("orders_full.csv")
stock = {(r.wid, r.Product_Name): r.stock for r in inv.itertuples()}
rem = {(r.wid, r.Product_Name): r.remaining_days for r in inv.itertuples()}
prods = sorted(inv.Product_Name.unique())

def make_batch():
    # same product per batch so orders compete for the same limited stock
    p = rng.choice(prods)
    rows = orders.sample(B, random_state=int(rng.integers(1e9)))
    return [dict(id=r.Order_ID, product=p, min_shelf=int(r.min_shelf_days),
                 dist={w: float(getattr(r, f"dist_{w}")) for w in W}) for r in rows.itertuples()]

def ok(o, w, used):
    k = (w, o["product"])
    return (stock.get(k, 0) - used.get(k, 0) > 0 and rem.get(k, 0) >= o["min_shelf"]
            and o["dist"][w] <= MAX_KM)

def cost(o, w):
    return o["dist"][w] + ALPHA * rem[(w, o["product"])]

def sequential(batch):                       # FEFO, order by order
    used, tot, plan = {}, 0.0, []
    for o in batch:
        c = [w for w in W if ok(o, w, used)]
        if not c: return None, None
        w = min(c, key=lambda w: (rem[(w, o["product"])], o["dist"][w]))
        used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1
        tot += cost(o, w); plan.append(w)
    return tot, plan

def joint_exact(batch):                      # brute force 3^4 = 81 combos
    best, bp = None, None
    for combo in itertools.product(W, repeat=len(batch)):
        used, feas, tot = {}, True, 0.0
        for o, w in zip(batch, combo):
            if not ok(o, w, used): feas = False; break
            used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1
            tot += cost(o, w)
        if feas and (best is None or tot < best): best, bp = tot, list(combo)
    return best, bp

batches, res = [], []
for i in range(N_BATCH):
    b = make_batch()
    sc, sp = sequential(b); jc, jp = joint_exact(b)
    batches.append(b)
    res.append(dict(batch=i, product=b[0]["product"], seq_cost=sc, seq_plan=sp, joint_cost=jc, joint_plan=jp))

json.dump(batches, open("batches.json", "w"))
df = pd.DataFrame(res); df.to_csv("baseline_results.csv", index=False)

solvable = df[df.joint_cost.notna()]
both = solvable[solvable.seq_cost.notna()]
print("batches:", len(df), "| solvable (joint feasible):", len(solvable))
print("sequential feasible on solvable:", len(both), "/", len(solvable))
print("mean joint cost:", round(both.joint_cost.mean(), 2), "| mean sequential cost:", round(both.seq_cost.mean(), 2))
print("batches where sequential is worse:", int((both.seq_cost > both.joint_cost + 1e-9).sum()), "/", len(both))
print("avg gap seq vs joint (%):", round(100 * ((both.seq_cost - both.joint_cost) / both.joint_cost).mean(), 2))