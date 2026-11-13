# qaoa_joint.py  (needs scipy: pip install scipy)
import json, time, itertools
import numpy as np, pandas as pd
from scipy.optimize import minimize

rng = np.random.default_rng(1)
ALPHA, MAX_KM, P_LAYERS, SHOTS, N_RUN, PEN = 0.1, 20, 2, 1024, 30, 100.0
W = ["A", "B", "C"]; B = 4; NQ = B * len(W)

inv = pd.read_csv("inventory.csv")
stock = {(r.wid, r.Product_Name): r.stock for r in inv.itertuples()}
rem = {(r.wid, r.Product_Name): r.remaining_days for r in inv.itertuples()}
batches = json.load(open("batches.json"))
base = pd.read_csv("baseline_results.csv")

def ok(o, w, used):
    k = (w, o["product"])
    return (stock.get(k, 0) - used.get(k, 0) > 0 and rem.get(k, 0) >= o["min_shelf"]
            and o["dist"][w] <= MAX_KM)
def cst(o, w): return o["dist"][w] + ALPHA * rem[(w, o["product"])]

BITS = ((np.arange(2**NQ)[:, None] >> (NQ - 1 - np.arange(NQ))) & 1)

def energy(batch):
    """Diagonal cost over all 2^12 bitstrings: objective + penalties. bit index = order*3 + warehouse."""
    E = np.zeros(2**NQ)
    for k, bits in enumerate(BITS):
        x = bits.reshape(B, 3); e = 0.0; used = {}
        for i, o in enumerate(batch):
            e += PEN * abs(x[i].sum() - 1)                       # one warehouse per order
            for j, w in enumerate(W):
                if x[i, j]:
                    key = (w, o["product"]); used[key] = used.get(key, 0) + 1
                    if stock.get(key, 0) < 1 or rem.get(key, 0) < o["min_shelf"] or o["dist"][w] > MAX_KM:
                        e += PEN                                  # shelf-life / distance / no stock
                    else:
                        e += cst(o, w)
        for key, u in used.items():
            e += PEN * max(0, u - stock.get(key, 0))             # stock limit
        E[k] = e
    return E

def feasible_plan(bits, batch):
    x = bits.reshape(B, 3)
    if not (x.sum(1) == 1).all(): return None
    plan = [W[int(np.argmax(x[i]))] for i in range(B)]
    used = {}
    for o, w in zip(batch, plan):
        if not ok(o, w, used): return None
        used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1
    return plan

def plan_cost(plan, batch): return sum(cst(o, w) for o, w in zip(batch, plan))

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

def repair_refine(sample_bits, batch):
    x = sample_bits.reshape(B, 3); plan = [None] * B; used = {}
    for i, o in enumerate(batch):                       # keep valid choices, fix the rest
        if x[i].sum() == 1:
            w = W[int(np.argmax(x[i]))]
            if ok(o, w, used): plan[i] = w; used[(w, o["product"])] = used.get((w, o["product"]), 0) + 1
    for i, o in enumerate(batch):
        if plan[i] is None:
            c = [w for w in W if ok(o, w, used)]
            if not c: return None
            plan[i] = min(c, key=lambda w: cst(o, w)); used[(plan[i], o["product"])] = used.get((plan[i], o["product"]), 0) + 1
    improved = True                                      # classical refine: single-order swaps
    while improved:
        improved = False
        for i, o in enumerate(batch):
            k_old = (plan[i], o["product"]); used[k_old] -= 1
            best = min([w for w in W if ok(o, w, used)] or [plan[i]], key=lambda w: cst(o, w))
            if cst(o, best) < cst(o, plan[i]) - 1e-9: plan[i] = best; improved = True
            used[(plan[i], o["product"])] = used.get((plan[i], o["product"]), 0) + 1
    return plan

rows = []
solv = base[base.joint_cost.notna()].head(N_RUN)
for r in solv.itertuples():
    batch = batches[r.batch]; E = energy(batch); t0 = time.time()
    f = lambda p: float(np.dot(qaoa(E, p), E))
    best = None
    for _ in range(2):                                   # 2 random restarts
        res = minimize(f, rng.uniform(0, np.pi, 2*P_LAYERS), method="COBYLA", options={"maxiter": 80})
        if best is None or res.fun < best.fun: best = res
    probs = qaoa(E, best.x)
    samp = rng.choice(2**NQ, SHOTS, p=probs / probs.sum())
    valid = [feasible_plan(BITS[k], batch) for k in samp]
    vrate = np.mean([v is not None for v in valid])
    qc = min([plan_cost(v, batch) for v in valid if v], default=None)       # quantum-only, no repair
    top = [k for k, _ in zip(np.argsort(-probs), range(20))]               # hybrid: top-20 -> repair -> refine
    hc = min([plan_cost(p, batch) for p in (repair_refine(BITS[k], batch) for k in top) if p], default=None)
    rows.append(dict(batch=r.batch, opt=r.joint_cost, seq=r.seq_cost, quantum=qc, hybrid=hc,
                     valid_rate=vrate, sec=round(time.time() - t0, 1)))
    print(r.batch, "opt", round(r.joint_cost, 2), "q", qc and round(qc, 2), "h", hc and round(hc, 2))

df = pd.DataFrame(rows); df.to_csv("qaoa_results.csv", index=False)
gap = lambda c: (100 * (df[c] - df.opt) / df.opt)[df[c].notna()]
print("\n--- SUMMARY (", len(df), "batches ) ---")
print("valid-sample rate:", round(100 * df.valid_rate.mean(), 1), "%")
for m in ["quantum", "hybrid"]:
    print(m, "| feasible:", int(df[m].notna().sum()), "| mean gap to optimum %:", round(gap(m).mean(), 2),
          "| optimal:", int((gap(m).abs() < 1e-6).sum()))
sq = df[df.seq.notna()]
print("sequential | feasible:", len(sq), "| mean gap %:", round((100*(sq.seq-sq.opt)/sq.opt).mean(), 2))
print("avg seconds/batch:", round(df.sec.mean(), 1))