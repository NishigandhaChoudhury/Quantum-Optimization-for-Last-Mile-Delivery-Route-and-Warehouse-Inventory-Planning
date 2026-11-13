# tune.py  (needs: pandas numpy matplotlib)
import copy, itertools
import numpy as np, pandas as pd

DAYS, PER_DAY, B = 30, 12, 4
MAX_KM, UNS, K = 25, 200.0, 15
LOST_ORDER_KM, EXPIRED_UNIT_KM = 30, 15      # assumed business weights (km-equivalent)
ALPHAS = [0, 0.05, 0.1, 0.2, 0.5, 1, 2, 5]
W = ["A", "B", "C"]
rng = np.random.default_rng(7)

inv = pd.read_csv("inventory.csv")
orders = pd.read_csv("orders_full.csv")
LOTS0 = {(r.wid, r.Product_Name): [int(r.stock) * K, int(r.remaining_days)] for r in inv.itertuples()}
TOTAL_UNITS = sum(v[0] for v in LOTS0.values())

day_orders = []
for d in range(DAYS):
    rows = orders.sample(PER_DAY, random_state=d)
    day_orders.append([dict(product=str(rng.choice(sorted(inv.Product_Name.unique()))),
                            min_shelf=int(r.min_shelf_days),
                            dist={w: float(getattr(r, f"dist_{w}")) for w in W}) for r in rows.itertuples()])

def feas(o, w, used, lots, d):
    k = (w, o["product"]); l = lots.get(k)
    return (l is not None and l[0] - used.get(k, 0) > 0 and l[1] - d >= o["min_shelf"]
            and o["dist"][w] <= MAX_KM)
def cst(o, w, lots, d, a): return o["dist"][w] + a * (lots[(w, o["product"])][1] - d)
def use(used, o, w): used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1

def seq(batch, lots, d, key):
    used, plan = {}, []
    for o in batch:
        c = [w for w in W if feas(o, w, used, lots, d)]
        if not c: plan.append(None); continue
        w = min(c, key=lambda w: key(o, w)); use(used, o, w); plan.append(w)
    return plan

def nearest(b, l, d): return seq(b, l, d, lambda o, w: o["dist"][w])
def fefo(b, l, d): return seq(b, l, d, lambda o, w: (l[(w, o["product"])][1] - d, o["dist"][w]))
def greedy(a): return lambda b, l, d: seq(b, l, d, lambda o, w: cst(o, w, l, d, a))

def joint(a):
    def run(batch, lots, d):
        best, bp = None, None
        for combo in itertools.product(W + [None], repeat=len(batch)):
            used, ok, t = {}, True, 0.0
            for o, w in zip(batch, combo):
                if w is None: t += UNS; continue
                if not feas(o, w, used, lots, d): ok = False; break
                use(used, o, w); t += cst(o, w, lots, d, a)
            if ok and (best is None or t < best): best, bp = t, list(combo)
        return bp
    return run

def simulate(policy, d0, d1):
    lots = copy.deepcopy(LOTS0); expired = km = served = unserved = 0
    for d in range(d0, d1):
        for l in lots.values():
            if l[1] - d <= 0 and l[0] > 0: expired += l[0]; l[0] = 0
        for i in range(0, PER_DAY, B):
            batch = day_orders[d][i:i+B]; plan = policy(batch, lots, d)
            for o, w in zip(batch, plan):
                if w: lots[(w, o["product"])][0] -= 1; km += o["dist"][w]; served += 1
                else: unserved += 1
    for l in lots.values():
        if l[1] - d1 <= 0 and l[0] > 0: expired += l[0]
    cost = km + LOST_ORDER_KM * unserved + EXPIRED_UNIT_KM * expired
    return dict(expired=expired, km=round(km, 1), km_per_order=round(km / max(served, 1), 2),
                served=served, unserved=unserved, total_cost=round(cost, 1))

fam = {"nearest": {"-": nearest}, "FEFO": {"-": fefo},
       "greedy-cost": {a: greedy(a) for a in ALPHAS},
       "joint-exact": {a: joint(a) for a in ALPHAS}}

rows = []
for f, variants in fam.items():
    for a, pol in variants.items():
        print("running", f, a, flush=True)
        tr = simulate(pol, 0, 15); te = simulate(pol, 15, 30)
        rows.append(dict(method=f, alpha=a, **{"tune_" + k: v for k, v in tr.items()},
                         **{"test_" + k: v for k, v in te.items()}))
df = pd.DataFrame(rows); df.to_csv("tune_results.csv", index=False)

print("\n=== ALL RUNS (tune = days 1-15, test = days 16-30) ===")
print(df[["method", "alpha", "tune_expired", "tune_unserved", "tune_total_cost",
          "test_expired", "test_unserved", "test_km_per_order", "test_total_cost"]].to_string(index=False))

print("\n=== BEST ALPHA PICKED ON TUNE DAYS, SCORED ON TEST DAYS ===")
pick = df.loc[df.groupby("method").tune_total_cost.idxmin()]
print(pick[["method", "alpha", "test_expired", "test_unserved", "test_km_per_order",
            "test_total_cost"]].sort_values("test_total_cost").to_string(index=False))
base = pick[pick.method == "nearest"].test_total_cost.iloc[0]
for r in pick.itertuples():
    print(f"{r.method}: {round(100 * (base - r.test_total_cost) / base, 1)}% lower test cost than nearest")

try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.figure(figsize=(7, 5))
    for f in fam:
        s = df[df.method == f]
        plt.scatter(s.test_km_per_order, s.test_expired, label=f, s=60)
    plt.xlabel("Avg km per order (test days)"); plt.ylabel("Units expired (test days)")
    plt.legend(); plt.title("Waste vs distance trade-off"); plt.tight_layout()
    plt.savefig("tradeoff.png", dpi=150); print("saved tradeoff.png")
except Exception as e:
    print("plot skipped:", e)