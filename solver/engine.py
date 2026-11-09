"""Solver engine (stateless): expiry-aware warehouse assignment with classical, QAOA and hybrid methods.
All data comes in through function arguments (the Node API sends it from MongoDB)."""
import copy, itertools, time
import numpy as np
from scipy.optimize import minimize

W = ["A", "B", "C"]
B = 4                       # orders per batch (4 orders x 3 warehouses = 12 qubits)
NQ = B * 3
DAYS = 30
MAX_KM = 25                 # delivery distance limit
UNS = 200.0                 # optimiser cost of leaving an order unserved
PEN, P_LAYERS, SHOTS = 100.0, 2, 1024
LOST_KM, EXP_KM, SPEED = 30, 15, 30.0
LAB_CAP = 3                 # quantum lab caps stock so the 4 orders compete
LABELS = {
    "nearest": "Nearest warehouse (today's practice)",
    "fefo": "Oldest stock first (FEFO)",
    "greedy": "Cost-aware greedy",
    "joint": "Joint exact (orders together)",
    "qaoa": "QAOA only (simulated)",
    "hybrid": "QAOA + repair + refine",
}


def lots_from(stock, cap=None):
    """stock: [{wid, product, units, days}] -> {(wid, product): [units, days]}"""
    return {(s["wid"], s["product"]): [min(int(s["units"]), cap) if cap else int(s["units"]), int(s["days"])]
            for s in stock}


def norm_order(o, product=None):
    return dict(id=str(o["id"]), product=product or o["product"], min_shelf=int(o["min_shelf"]),
                dist={w: float(o["dist"][w]) for w in W}, lat=o.get("lat"), lon=o.get("lon"))


def make_days(pool, per_day, seed):
    out = []
    for d in range(DAYS):
        idx = np.random.default_rng(seed * 100 + d).choice(len(pool), per_day, replace=False)
        out.append([norm_order(pool[i]) for i in idx])
    return out


# ---------------- core rules ----------------
def feas(o, w, used, lots, d):
    k = (w, o["product"]); l = lots.get(k)
    return (l is not None and l[0] - used.get(k, 0) > 0 and l[1] - d >= o["min_shelf"]
            and o["dist"][w] <= MAX_KM)

def cst(o, w, lots, d, a):
    return o["dist"][w] + a * (lots[(w, o["product"])][1] - d)

def use(used, o, w):
    used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1

def total(plan, batch, lots, d, a):
    return sum(cst(o, w, lots, d, a) if w else UNS for o, w in zip(batch, plan))


# ---------------- classical policies ----------------
def seq(batch, lots, d, key):
    used, plan = {}, []
    for o in batch:
        c = [w for w in W if feas(o, w, used, lots, d)]
        if not c:
            plan.append(None); continue
        w = min(c, key=lambda w: key(o, w)); use(used, o, w); plan.append(w)
    return plan

def nearest(b, l, d): return seq(b, l, d, lambda o, w: o["dist"][w])
def fefo(b, l, d): return seq(b, l, d, lambda o, w: (l[(w, o["product"])][1] - d, o["dist"][w]))
def greedy(a): return lambda b, l, d: seq(b, l, d, lambda o, w: cst(o, w, l, d, a))

def joint(a):
    def run(batch, lots, d):
        best, bp = None, [None] * len(batch)
        for combo in itertools.product(W + [None], repeat=len(batch)):
            used, ok, t = {}, True, 0.0
            for o, w in zip(batch, combo):
                if w is None:
                    t += UNS; continue
                if not feas(o, w, used, lots, d):
                    ok = False; break
                use(used, o, w); t += cst(o, w, lots, d, a)
            if ok and (best is None or t < best):
                best, bp = t, list(combo)
        return bp
    return run


# ---------------- quantum (numpy QAOA simulator) ----------------
BITS = ((np.arange(2 ** NQ)[:, None] >> (NQ - 1 - np.arange(NQ))) & 1)

def energy(batch, lots, d, a):
    E = np.zeros(2 ** NQ)
    for k, bits in enumerate(BITS):
        x = bits.reshape(B, 3); e = 0.0; used = {}
        for i, o in enumerate(batch):
            e += PEN * abs(x[i].sum() - 1)
            for j, w in enumerate(W):
                if x[i, j]:
                    use(used, o, w)
                    e += cst(o, w, lots, d, a) if feas(o, w, {}, lots, d) else PEN
        for (w, p), u in used.items():
            l = lots.get((w, p)); e += PEN * max(0, u - (l[0] if l else 0))
        E[k] = e
    return E

def qaoa_probs(E, params):
    Cn = E / E.max(); psi = np.ones(2 ** NQ, complex) / np.sqrt(2 ** NQ)
    for l in range(P_LAYERS):
        psi = psi * np.exp(-1j * params[2 * l] * Cn)
        psi = psi.reshape((2,) * NQ); c, s = np.cos(params[2 * l + 1]), np.sin(params[2 * l + 1])
        for q in range(NQ):
            a0, a1 = np.take(psi, 0, q), np.take(psi, 1, q)
            psi = np.stack([c * a0 - 1j * s * a1, -1j * s * a0 + c * a1], axis=q)
        psi = psi.reshape(-1)
    return np.abs(psi) ** 2

def valid_plan(bits, batch, lots, d):
    x = bits.reshape(B, 3)
    if not (x.sum(1) == 1).all():
        return None
    plan, used = [], {}
    for i, o in enumerate(batch):
        w = W[int(np.argmax(x[i]))]
        if not feas(o, w, used, lots, d):
            return None
        use(used, o, w); plan.append(w)
    return plan

def repair_refine(bits, batch, lots, d, a):
    x = bits.reshape(B, 3); plan = [None] * B; used = {}
    for i, o in enumerate(batch):
        if x[i].sum() == 1:
            w = W[int(np.argmax(x[i]))]
            if feas(o, w, used, lots, d):
                plan[i] = w; use(used, o, w)
    for i, o in enumerate(batch):
        if plan[i] is None:
            c = [w for w in W if feas(o, w, used, lots, d)]
            if c:
                plan[i] = min(c, key=lambda w: cst(o, w, lots, d, a)); use(used, o, plan[i])
    for _ in range(5):
        changed = False
        for i, o in enumerate(batch):
            if plan[i] is None:
                continue
            used[(plan[i], o["product"])] -= 1
            c = [w for w in W if feas(o, w, used, lots, d)]
            b = min(c, key=lambda w: cst(o, w, lots, d, a))
            if cst(o, b, lots, d, a) < cst(o, plan[i], lots, d, a) - 1e-9:
                plan[i] = b; changed = True
            use(used, o, plan[i])
        if not changed:
            break
    return plan

def qaoa_solve(batch, lots, d, a, rng):
    E = energy(batch, lots, d, a)
    f = lambda p: float(np.dot(qaoa_probs(E, p), E))
    r = min((minimize(f, rng.uniform(0, np.pi, 2 * P_LAYERS), method="COBYLA", options={"maxiter": 60})
             for _ in range(2)), key=lambda r: r.fun)
    return qaoa_probs(E, r.x)

def quantum_policy(a, hybrid, rng):
    def run(batch, lots, d):
        probs = qaoa_solve(batch, lots, d, a, rng)
        if hybrid:
            plans = [repair_refine(BITS[k], batch, lots, d, a) for k in np.argsort(-probs)[:20]]
        else:
            samp = rng.choice(2 ** NQ, SHOTS, p=probs / probs.sum())
            plans = [p for p in (valid_plan(BITS[k], batch, lots, d) for k in samp) if p]
        return min(plans, key=lambda p: total(p, batch, lots, d, a)) if plans else [None] * len(batch)
    return run


# ---------------- 30-day simulation ----------------
def simulate(policy, days, per_day, lots0):
    lots = copy.deepcopy(lots0); expired = km = served = unserved = 0
    for d in range(DAYS):
        for l in lots.values():
            if l[1] - d <= 0 and l[0] > 0:
                expired += l[0]; l[0] = 0
        for i in range(0, per_day, B):
            batch = days[d][i:i + B]; plan = policy(batch, lots, d)
            for o, w in zip(batch, plan):
                if w:
                    lots[(w, o["product"])][0] -= 1; km += o["dist"][w]; served += 1
                else:
                    unserved += 1
    for l in lots.values():
        if l[1] - DAYS <= 0 and l[0] > 0:
            expired += l[0]
    kpo = km / max(served, 1)
    return dict(expired=expired, unserved=unserved, served=served, km_per_order=kpo,
                minutes_per_order=kpo / SPEED * 60, total_cost=km + LOST_KM * unserved + EXP_KM * expired)

def run_benchmark(pool, stock, per_day, n_seeds, ag, aj, aq, include_q, q_seeds, progress=lambda f, m: None):
    if per_day % B:
        raise ValueError("Orders per day must be a multiple of 4.")
    if len(pool) < per_day:
        raise ValueError("Not enough orders in the database for this daily volume.")
    lots0 = lots_from(stock)
    methods = ["nearest", "fefo", "greedy", "joint"] + (["qaoa", "hybrid"] if include_q else [])
    q_seeds = min(q_seeds, n_seeds)
    steps = n_seeds * 4 + (q_seeds * 2 if include_q else 0); done = 0; raw = {m: {} for m in methods}
    for s in range(n_seeds):
        days = make_days(pool, per_day, s); rng = np.random.default_rng(1000 + s)
        pols = {"nearest": nearest, "fefo": fefo, "greedy": greedy(ag), "joint": joint(aj),
                "qaoa": quantum_policy(aq, False, rng), "hybrid": quantum_policy(aq, True, rng)}
        for m in methods:
            if m in ("qaoa", "hybrid") and s >= q_seeds:
                continue
            progress(done / steps, f"run {s + 1}/{n_seeds}: {LABELS[m]}")
            raw[m][s] = simulate(pols[m], days, per_day, lots0); done += 1
    rows = []
    for m in methods:
        seeds = sorted(raw[m]); r = [raw[m][s] for s in seeds]
        near = [raw["nearest"][s]["total_cost"] for s in seeds]
        pct = [100 * (n - x["total_cost"]) / n for n, x in zip(near, r)]
        f = lambda key: (float(np.mean([x[key] for x in r])), float(np.std([x[key] for x in r])))
        rows.append(dict(method=m, label=LABELS[m], runs=len(seeds), expired=f("expired"), unserved=f("unserved"),
                         km_per_order=f("km_per_order"), minutes_per_order=f("minutes_per_order"),
                         total_cost=f("total_cost"), pct_vs_nearest=float(np.mean(pct)),
                         better_runs=int(sum(p > 0 for p in pct))))
    progress(1.0, "done")
    return dict(per_day=per_day, n_seeds=n_seeds, total_units=int(sum(v[0] for v in lots0.values())),
                orders=per_day * DAYS, alphas=dict(greedy=ag, joint=aj, quantum=aq), rows=rows,
                assumptions=dict(lost_order_km=LOST_KM, expired_unit_km=EXP_KM, speed_kmh=SPEED, max_km=MAX_KM))


# ---------------- live planner ----------------
def plan_batch(orders, stock, ag, aj):
    lots = lots_from(stock); batch = [norm_order(o) for o in orders]; out = {}
    for name, pol in [("nearest", nearest), ("fefo", fefo), ("greedy", greedy(ag)), ("joint", joint(aj))]:
        plan = pol(batch, lots, 0)
        ship = [(o, w) for o, w in zip(batch, plan) if w]
        out[name] = dict(label=LABELS[name], plan=plan,
                         km=round(sum(o["dist"][w] for o, w in ship), 2), unserved=plan.count(None),
                         avg_days_left=round(float(np.mean([lots[(w, o["product"])][1] for o, w in ship])), 1) if ship else None)
    prods = sorted({o["product"] for o in batch})
    shelf = [dict(product=p, wid=w, units=lots[(w, p)][0], days=lots[(w, p)][1]) for p in prods for w in W if (w, p) in lots]
    return dict(plans=out, shelf=shelf)


# ---------------- quantum lab ----------------
def quantum_lab(seed, pool, stock, aq=0.1):
    lots = lots_from(stock, cap=LAB_CAP); t0 = time.time()
    prods = sorted({p for (_, p) in lots if sum((w, p) in lots for w in W) >= 2})
    if not prods or len(pool) < B:
        return dict(error="Not enough stock or orders for the quantum lab.")
    batch = best = None
    for attempt in range(40):
        rng = np.random.default_rng(seed * 50 + attempt); product = str(rng.choice(prods))
        idx = rng.choice(len(pool), B, replace=False)
        batch = [norm_order(pool[i], product) for i in idx]
        best = None
        for combo in itertools.product(W, repeat=B):
            used, ok = {}, True
            for o, w in zip(batch, combo):
                if not feas(o, w, used, lots, 0):
                    ok = False; break
                use(used, o, w)
            if ok:
                t = total(combo, batch, lots, 0, aq)
                if best is None or t < best[0]:
                    best = (t, list(combo))
        if best:
            break
    if not best:
        return dict(error="No feasible batch found. Try another batch number.")
    rng = np.random.default_rng(seed)
    probs = qaoa_solve(batch, lots, 0, aq, rng)
    samp = rng.choice(2 ** NQ, SHOTS, p=probs / probs.sum())
    valid = [p for p in (valid_plan(BITS[k], batch, lots, 0) for k in samp) if p]
    qplan = min(valid, key=lambda p: total(p, batch, lots, 0, aq)) if valid else None
    hplans = [repair_refine(BITS[k], batch, lots, 0, aq) for k in np.argsort(-probs)[:20]]
    hplans = [p for p in hplans if None not in p]
    hplan = min(hplans, key=lambda p: total(p, batch, lots, 0, aq)) if hplans else None
    rand_rate = sum(valid_plan(b, batch, lots, 0) is not None for b in BITS) / 2 ** NQ
    top = []
    for k in np.argsort(-probs)[:10]:
        p = valid_plan(BITS[k], batch, lots, 0)
        top.append(dict(bits="".join(map(str, BITS[k])), prob=float(probs[k]), valid=p is not None,
                        cost=round(total(p, batch, lots, 0, aq), 2) if p else None))
    def pack(p):
        if not p:
            return None
        c = total(p, batch, lots, 0, aq)
        return dict(plan=p, cost=round(c, 2), gap_pct=round(100 * (c - best[0]) / best[0], 2))
    return dict(product=batch[0]["product"], orders=batch, exact=dict(plan=best[1], cost=round(best[0], 2), gap_pct=0.0),
                qaoa=pack(qplan), hybrid=pack(hplan), valid_rate=len(valid) / SHOTS, random_valid_rate=rand_rate,
                top=top, seconds=round(time.time() - t0, 1), qubits=NQ, layers=P_LAYERS, shots=SHOTS,
                stock_cap=LAB_CAP)
