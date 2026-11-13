# multi_seed.py  (needs: pandas numpy matplotlib)
import copy, itertools
import numpy as np, pandas as pd

DAYS, B = 30, 4
MAX_KM, UNS, K = 25, 200.0, 15
LOST_KM, EXP_KM = 30, 15                      # assumed km-equivalent costs
ALPHAS = [0, 0.1, 0.2, 0.5, 1, 2]
LEVELS = {"low (360 orders)": 12, "high (720 orders)": 24}
TUNE_SEEDS, TEST_SEEDS = range(0, 5), range(5, 10)
W = ["A", "B", "C"]

inv = pd.read_csv("inventory.csv")
orders = pd.read_csv("orders_full.csv")
PRODS = sorted(inv.Product_Name.unique())
LOTS0 = {(r.wid, r.Product_Name): [int(r.stock) * K, int(r.remaining_days)] for r in inv.itertuples()}
TOTAL_UNITS = sum(v[0] for v in LOTS0.values())

def make_days(per_day, seed):
    rng = np.random.default_rng(seed)
    out = []
    for d in range(DAYS):
        rows = orders.sample(per_day, random_state=seed * 100 + d)
        out.append([dict(product=str(rng.choice(PRODS)), min_shelf=int(r.min_shelf_days),
                         dist={w: float(getattr(r, f"dist_{w}")) for w in W}) for r in rows.itertuples()])
    return out

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

def simulate(policy, days, per_day):
    lots = copy.deepcopy(LOTS0); expired = km = served = unserved = 0
    for d in range(DAYS):
        for l in lots.values():
            if l[1] - d <= 0 and l[0] > 0: expired += l[0]; l[0] = 0
        for i in range(0, per_day, B):
            batch = days[d][i:i+B]; plan = policy(batch, lots, d)
            for o, w in zip(batch, plan):
                if w: lots[(w, o["product"])][0] -= 1; km += o["dist"][w]; served += 1
                else: unserved += 1
    for l in lots.values():
        if l[1] - DAYS <= 0 and l[0] > 0: expired += l[0]
    return dict(expired=expired, unserved=unserved, km_per_order=km / max(served, 1),
                total_cost=km + LOST_KM * unserved + EXP_KM * expired)

fam = {"nearest": {"-": nearest}, "FEFO": {"-": fefo},
       "greedy-cost": {a: greedy(a) for a in ALPHAS},
       "joint-exact": {a: joint(a) for a in ALPHAS}}

rows = []
for lvl, per_day in LEVELS.items():
    cache = {s: make_days(per_day, s) for s in range(10)}
    for f, variants in fam.items():
        for a, pol in variants.items():
            print("running", lvl, f, a, flush=True)
            for s in range(10):
                rows.append(dict(level=lvl, method=f, alpha=a, seed=s, **simulate(pol, cache[s], per_day)))
df = pd.DataFrame(rows); df.to_csv("multi_seed_raw.csv", index=False)

final = []
for lvl in LEVELS:
    print(f"\n=========== DEMAND: {lvl} | total stock units: {TOTAL_UNITS} ===========")
    d0 = df[df.level == lvl]
    chosen = {}
    for f in fam:
        t = d0[(d0.method == f) & d0.seed.isin(TUNE_SEEDS)].groupby("alpha", sort=False).total_cost.mean()
        chosen[f] = t.idxmin()                                  # alpha picked on seeds 0-4 only
    print("alpha picked on tune seeds 0-4:", {k: v for k, v in chosen.items() if k in ("greedy-cost", "joint-exact")})
    near = d0[(d0.method == "nearest") & d0.seed.isin(TEST_SEEDS)].set_index("seed").total_cost
    for f in fam:
        s = d0[(d0.method == f) & (d0.alpha == chosen[f]) & d0.seed.isin(TEST_SEEDS)].set_index("seed")
        red = 100 * (near - s.total_cost) / near
        final.append(dict(level=lvl, method=f, alpha=chosen[f],
                          expired=f"{s.expired.mean():.1f} ± {s.expired.std():.1f}",
                          unserved=f"{s.unserved.mean():.1f} ± {s.unserved.std():.1f}",
                          km_per_order=f"{s.km_per_order.mean():.2f}",
                          total_cost=f"{s.total_cost.mean():.0f} ± {s.total_cost.std():.0f}",
                          pct_cost_vs_nearest=f"{red.mean():.1f}%",
                          seeds_better_than_nearest=f"{int((s.total_cost < near).sum())}/5"))
    print(pd.DataFrame([r for r in final if r["level"] == lvl]).drop(columns="level").to_string(index=False))
pd.DataFrame(final).to_csv("multi_seed_summary.csv", index=False)

try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for a, lvl in zip(ax, LEVELS):
        r = [x for x in final if x["level"] == lvl]
        a.bar([x["method"] for x in r], [float(x["total_cost"].split(" ")[0]) for x in r])
        a.set_title(lvl + ": mean test cost (lower is better)"); a.tick_params(axis="x", rotation=20)
    plt.tight_layout(); plt.savefig("multi_seed.png", dpi=150); print("saved multi_seed.png")
except Exception as e:
    print("plot skipped:", e)