# simulate.py  (pip install matplotlib scipy)
import copy, time, itertools
import numpy as np, pandas as pd
from scipy.optimize import minimize

DAYS, PER_DAY, B = 30, 12, 4
ALPHA, MAX_KM, UNS, PEN, K = 0.1, 25, 200.0, 100.0, 15   # K = stock scale-up
P_LAYERS, SHOTS = 2, 1024
W = ["A", "B", "C"]; NQ = B * 3
rng = np.random.default_rng(7)

inv = pd.read_csv("inventory.csv")
orders = pd.read_csv("orders_full.csv")
LOTS0 = {(r.wid, r.Product_Name): [int(r.stock) * K, int(r.remaining_days)] for r in inv.itertuples()}
TOTAL_UNITS = sum(v[0] for v in LOTS0.values())

def feas(o, w, used, lots, d):
    k = (w, o["product"]); l = lots.get(k)
    return (l is not None and l[0] - used.get(k, 0) > 0 and l[1] - d >= o["min_shelf"]
            and o["dist"][w] <= MAX_KM)
def cst(o, w, lots, d): return o["dist"][w] + ALPHA * (lots[(w, o["product"])][1] - d)
def use(used, o, w): used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1
def total(plan, batch, lots, d):
    return sum(cst(o, w, lots, d) if w else UNS for o, w in zip(batch, plan))

# ---------- classical policies ----------
def seq_policy(batch, lots, d, key):
    used, plan = {}, []
    for o in batch:
        c = [w for w in W if feas(o, w, used, lots, d)]
        if not c: plan.append(None); continue
        w = min(c, key=lambda w: key(o, w, lots, d)); use(used, o, w); plan.append(w)
    return plan
def nearest(batch, lots, d): return seq_policy(batch, lots, d, lambda o, w, l, d: o["dist"][w])
def fefo(batch, lots, d):
    return seq_policy(batch, lots, d, lambda o, w, l, d: (l[(w, o["product"])][1] - d, o["dist"][w]))
def joint_exact(batch, lots, d):
    best, bp = None, None
    for combo in itertools.product(W + [None], repeat=len(batch)):
        used, ok = {}, True
        for o, w in zip(batch, combo):
            if w is None: continue
            if not feas(o, w, used, lots, d): ok = False; break
            use(used, o, w)
        if ok:
            t = total(combo, batch, lots, d)
            if best is None or t < best: best, bp = t, list(combo)
    return bp

# ---------- quantum ----------
BITS = ((np.arange(2**NQ)[:, None] >> (NQ - 1 - np.arange(NQ))) & 1)
def energy(batch, lots, d):
    E = np.zeros(2**NQ)
    for k, bits in enumerate(BITS):
        x = bits.reshape(B, 3); e = 0.0; used = {}
        for i, o in enumerate(batch):
            e += PEN * abs(x[i].sum() - 1)
            for j, w in enumerate(W):
                if x[i, j]:
                    use(used, o, w)
                    e += cst(o, w, lots, d) if feas(o, w, {}, lots, d) else PEN
        for (w, p), u in used.items():
            l = lots.get((w, p)); e += PEN * max(0, u - (l[0] if l else 0))
        E[k] = e
    return E
def qaoa(E, params):
    Cn = E / E.max(); psi = np.ones(2**NQ, complex) / np.sqrt(2**NQ)
    for l in range(P_LAYERS):
        psi = psi * np.exp(-1j * params[2*l] * Cn)
        psi = psi.reshape((2,) * NQ); c, s = np.cos(params[2*l+1]), np.sin(params[2*l+1])
        for q in range(NQ):
            a0, a1 = np.take(psi, 0, q), np.take(psi, 1, q)
            psi = np.stack([c*a0 - 1j*s*a1, -1j*s*a0 + c*a1], axis=q)
        psi = psi.reshape(-1)
    return np.abs(psi) ** 2
def valid_plan(bits, batch, lots, d):
    x = bits.reshape(B, 3)
    if not (x.sum(1) == 1).all(): return None
    plan, used = [], {}
    for i, o in enumerate(batch):
        w = W[int(np.argmax(x[i]))]
        if not feas(o, w, used, lots, d): return None
        use(used, o, w); plan.append(w)
    return plan
def repair_refine(bits, batch, lots, d):
    x = bits.reshape(B, 3); plan = [None] * B; used = {}
    for i, o in enumerate(batch):
        if x[i].sum() == 1:
            w = W[int(np.argmax(x[i]))]
            if feas(o, w, used, lots, d): plan[i] = w; use(used, o, w)
    for i, o in enumerate(batch):
        if plan[i] is None:
            c = [w for w in W if feas(o, w, used, lots, d)]
            if c: plan[i] = min(c, key=lambda w: cst(o, w, lots, d)); use(used, o, plan[i])
    for _ in range(5):                                  # classical refine: single swaps
        changed = False
        for i, o in enumerate(batch):
            if plan[i] is None: continue
            used[(plan[i], o["product"])] -= 1
            c = [w for w in W if feas(o, w, used, lots, d)]
            b = min(c, key=lambda w: cst(o, w, lots, d))
            if cst(o, b, lots, d) < cst(o, plan[i], lots, d) - 1e-9: plan[i] = b; changed = True
            use(used, o, plan[i])
        if not changed: break
    return plan
def quantum_policy(batch, lots, d, hybrid):
    E = energy(batch, lots, d)
    f = lambda p: float(np.dot(qaoa(E, p), E))
    r = min((minimize(f, rng.uniform(0, np.pi, 2*P_LAYERS), method="COBYLA", options={"maxiter": 60})
             for _ in range(2)), key=lambda r: r.fun)
    probs = qaoa(E, r.x)
    if hybrid:
        top = np.argsort(-probs)[:20]
        plans = [repair_refine(BITS[k], batch, lots, d) for k in top]
    else:
        samp = rng.choice(2**NQ, SHOTS, p=probs / probs.sum())
        plans = [p for p in (valid_plan(BITS[k], batch, lots, d) for k in samp) if p]
    return min(plans, key=lambda p: total(p, batch, lots, d)) if plans else [None] * len(batch)

POLICIES = {
    "nearest (today's practice)": nearest,
    "sequential FEFO": fefo,
    "joint exact": joint_exact,
    "quantum-only (QAOA)": lambda b, l, d: quantum_policy(b, l, d, False),
    "hybrid (QAOA+repair+refine)": lambda b, l, d: quantum_policy(b, l, d, True),
}

# ---------- simulation ----------
day_orders = []
for d in range(DAYS):
    rows = orders.sample(PER_DAY, random_state=d)
    day_orders.append([dict(product=str(rng.choice(sorted(inv.Product_Name.unique()))),
                            min_shelf=int(r.min_shelf_days),
                            dist={w: float(getattr(r, f"dist_{w}")) for w in W}) for r in rows.itertuples()])

def simulate(policy):
    lots = copy.deepcopy(LOTS0); expired = km = served = unserved = 0; t0 = time.time()
    for d in range(DAYS):
        for k, l in lots.items():                         # expire stock
            if l[1] - d <= 0 and l[0] > 0: expired += l[0]; l[0] = 0
        for i in range(0, PER_DAY, B):
            batch = day_orders[d][i:i+B]; plan = policy(batch, lots, d)
            for o, w in zip(batch, plan):
                if w: lots[(w, o["product"])][0] -= 1; km += o["dist"][w]; served += 1
                else: unserved += 1
    for k, l in lots.items():                             # final-day expiry
        if l[1] - DAYS <= 0 and l[0] > 0: expired += l[0]
    return dict(units_expired=expired, waste_pct=round(100 * expired / TOTAL_UNITS, 1),
                total_km=round(km, 1), km_per_order=round(km / max(served, 1), 2),
                avg_minutes=round(km / max(served, 1) * 2, 1),   # 30 km/h average speed
                served=served, unserved=unserved, seconds=round(time.time() - t0, 1))

res = {}
for name, pol in POLICIES.items():
    print("running:", name, flush=True); res[name] = simulate(pol)
df = pd.DataFrame(res).T; df.to_csv("sim_results.csv")
print("\nTotal stock units:", TOTAL_UNITS, "| orders:", DAYS * PER_DAY)
print(df.to_string())

try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    for a, c, t in zip(ax, ["units_expired", "km_per_order", "unserved"],
                       ["Units expired (waste)", "Avg km per order", "Unserved orders"]):
        a.bar(range(len(df)), df[c].astype(float)); a.set_title(t)
        a.set_xticks(range(len(df))); a.set_xticklabels(["nearest", "FEFO", "joint", "QAOA", "hybrid"])
    plt.tight_layout(); plt.savefig("sim_results.png", dpi=150); print("saved sim_results.png")
except Exception as e:
    print("plot skipped:", e)