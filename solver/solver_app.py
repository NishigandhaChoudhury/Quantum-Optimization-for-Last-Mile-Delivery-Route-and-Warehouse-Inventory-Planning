"""Python solver service. Run:  python solver_app.py   (port 8001)"""
import threading, uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import engine

app = FastAPI(title="Expiry planner solver")
JOBS = {}


class Bench(BaseModel):
    pool: list
    stock: list
    per_day: int = 12
    runs: int = 5
    alpha_greedy: float = 2.0
    alpha_joint: float = 1.0
    alpha_quantum: float = 1.0
    include_quantum: bool = False
    quantum_runs: int = 1

class Plan(BaseModel):
    orders: list
    stock: list
    alpha_greedy: float = 2.0
    alpha_joint: float = 1.0

class Lab(BaseModel):
    seed: int = 1
    pool: list
    stock: list


@app.get("/health")
def health():
    return dict(ok=True)

@app.post("/benchmark")
def benchmark(r: Bench):
    if r.per_day % 4 or not 4 <= r.per_day <= 40:
        raise HTTPException(400, "Orders per day must be a multiple of 4 between 4 and 40.")
    if not 1 <= r.runs <= 10:
        raise HTTPException(400, "Runs must be between 1 and 10.")
    jid = uuid.uuid4().hex[:8]
    JOBS[jid] = dict(status="running", progress=0.0, message="starting", result=None, error=None)

    def work():
        try:
            res = engine.run_benchmark(r.pool, r.stock, r.per_day, r.runs, r.alpha_greedy, r.alpha_joint,
                                       r.alpha_quantum, r.include_quantum, r.quantum_runs,
                                       lambda f, m: JOBS[jid].update(progress=f, message=m))
            JOBS[jid].update(status="done", result=res, progress=1.0)
        except Exception as e:
            JOBS[jid].update(status="error", error=str(e))
    threading.Thread(target=work, daemon=True).start()
    return dict(job=jid)

@app.get("/job/{jid}")
def job(jid: str):
    if jid not in JOBS:
        raise HTTPException(404, "Unknown job")
    return JOBS[jid]

@app.post("/plan")
def plan(r: Plan):
    if not 1 <= len(r.orders) <= 4:
        raise HTTPException(400, "Plan 1 to 4 orders at a time.")
    return engine.plan_batch(r.orders, r.stock, r.alpha_greedy, r.alpha_joint)

@app.post("/quantum")
def quantum(r: Lab):
    return engine.quantum_lab(r.seed, r.pool, r.stock)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
