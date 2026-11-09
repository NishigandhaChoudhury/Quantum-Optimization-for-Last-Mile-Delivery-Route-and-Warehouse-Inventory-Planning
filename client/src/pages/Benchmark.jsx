import { useEffect, useRef, useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { api } from '../api.js';
import { fmt } from '../ui.jsx';

export default function Benchmark() {
  const [f, setF] = useState({ per_day: 12, runs: 5, alpha_greedy: 2, alpha_joint: 1, include_quantum: false, quantum_runs: 1 });
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState({ p: 0, m: '' });
  const [err, setErr] = useState('');
  const [R, setR] = useState(null);
  const [saved, setSaved] = useState(false);
  const [hist, setHist] = useState([]);
  const alive = useRef(true);
  useEffect(() => () => { alive.current = false; }, []);
  const loadHist = () => api('/benchmarks').then(async (h) => { setHist(h.items); if (h.items[0] && !R) { setR((await api('/benchmarks/' + h.items[0].id)).result); setSaved(true); } });
  useEffect(() => { loadHist().catch(() => {}); }, []);
  const run = async () => {
    setErr(''); setBusy(true); setSaved(false);
    try {
      const { job } = await api('/benchmark', { body: f });
      for (;;) {
        const j = await api('/job/' + job);
        if (!alive.current) return;
        setProg({ p: j.progress, m: j.message });
        if (j.status === 'done') { setR(j.result); loadHist(); break; }
        if (j.status === 'error') throw new Error(j.error);
        await new Promise((r) => setTimeout(r, 1500));
      }
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const open = async (id) => { if (id) { setR((await api('/benchmarks/' + id)).result); setSaved(true); } };
  const rows = R?.rows || [];
  const near = rows.find((r) => r.method === 'nearest');
  const best = rows.slice().sort((a, b) => a.total_cost[0] - b.total_cost[0])[0];
  const q = rows.filter((r) => r.method === 'qaoa' || r.method === 'hybrid').sort((a, b) => a.total_cost[0] - b.total_cost[0])[0];
  const col = rows.map((r) => r.method === 'nearest' ? '#9db5ba' : (r.method === 'qaoa' || r.method === 'hybrid') ? '#8a5fb0' : '#2f6f9f');
  const bar = (key) => <Bar data={{ labels: rows.map((r) => r.label.split(' (')[0]), datasets: [{ data: rows.map((r) => r[key][0]), backgroundColor: col }] }}
    options={{ plugins: { legend: { display: false } }, scales: { x: { ticks: { maxRotation: 60, minRotation: 40, font: { size: 10 } } } } }} />;
  const A = R?.assumptions;
  return (
    <>
      <h2>Benchmark</h2>
      <p className="sub">Replays 30 days of orders for every method on the same orders, starting from the current stock. Today's practice is shipping from the nearest warehouse.</p>
      <div className="card">
        <div className="row">
          <label>Orders per day<select value={f.per_day} onChange={(e) => setF({ ...f, per_day: +e.target.value })}><option value="12">12 (about 360 orders)</option><option value="24">24 (about 720 orders)</option></select></label>
          <label>Random runs<input type="number" min="1" max="10" value={f.runs} onChange={(e) => setF({ ...f, runs: +e.target.value })} /></label>
          <label>Expiry weight, greedy<input type="number" step="0.1" value={f.alpha_greedy} onChange={(e) => setF({ ...f, alpha_greedy: +e.target.value })} /></label>
          <label>Expiry weight, joint<input type="number" step="0.1" value={f.alpha_joint} onChange={(e) => setF({ ...f, alpha_joint: +e.target.value })} /></label>
        </div>
        <div className="row">
          <label className="chk"><input type="checkbox" checked={f.include_quantum} onChange={(e) => setF({ ...f, include_quantum: e.target.checked })} /> Include QAOA and hybrid (slow)</label>
          <label>Quantum runs<input type="number" min="1" max="3" value={f.quantum_runs} onChange={(e) => setF({ ...f, quantum_runs: +e.target.value })} /></label>
          <button className="act" disabled={busy} onClick={run}>Run benchmark</button>
          {hist.length > 0 && <label>Past runs<select onChange={(e) => open(e.target.value)} defaultValue=""><option value="">Open a saved run</option>
            {hist.map((h) => <option key={h.id} value={h.id}>{new Date(h.createdAt).toLocaleString()}, {h.params.per_day * 30} orders, {h.params.runs} runs</option>)}</select></label>}
        </div>
        {busy && <div className="bar"><i style={{ width: prog.p * 100 + '%' }} /></div>}
        <div className="note">{busy ? prog.m : ''}</div><div className="err">{err}</div>
      </div>
      {!R ? <div className="empty">No results yet. Run the benchmark to generate them.</div> : <>
        {saved && <p className="note">Showing a saved run.</p>}
        {best.method === 'nearest'
          ? <div className="card verdict warn"><h3>Today's practice was cheapest in this run</h3>No expiry-aware method beat shipping from the nearest warehouse. Try another expiry weight or a higher order volume.</div>
          : <div className="card verdict"><h3>{best.label} was the cheapest</h3>Total cost fell {best.pct_vs_nearest.toFixed(1)}% against shipping from the nearest warehouse, and it won in {best.better_runs} of {best.runs} runs.
            Units expired dropped from {near.expired[0].toFixed(0)} to {best.expired[0].toFixed(0)}, and unserved orders from {near.unserved[0].toFixed(0)} to {best.unserved[0].toFixed(0)},
            at {best.km_per_order[0].toFixed(2)} km per order against {near.km_per_order[0].toFixed(2)}.</div>}
        {q && <div className={'card verdict' + (q.total_cost[0] <= best.total_cost[0] ? '' : ' warn')}><h3>Quantum result</h3>{q.label} ran on {q.runs} run(s) and changed total cost by {q.pct_vs_nearest.toFixed(1)}% against nearest, compared with {best.pct_vs_nearest.toFixed(1)}% for {best.label}.{' '}
          {q.total_cost[0] <= best.total_cost[0] ? 'It matched or beat the classical methods here.' : 'It did not beat the best classical method, so the quantum solver adds no gain at this size.'}</div>}
        <div className="card scroll"><h3>Results, mean ± spread over runs</h3>
          <table><thead><tr><th>Method</th><th className="n">Runs</th><th className="n">Units expired</th><th className="n">Unserved orders</th><th className="n">Km per order</th><th className="n">Minutes per order</th><th className="n">Total cost</th><th className="n">Cost vs nearest</th><th className="n">Runs better</th></tr></thead>
            <tbody>{rows.map((r) => <tr key={r.method}><td>{r.label}</td><td className="n">{r.runs}</td><td className="n">{fmt(...r.expired)}</td><td className="n">{fmt(...r.unserved)}</td>
              <td className="n">{r.km_per_order[0].toFixed(2)}</td><td className="n">{r.minutes_per_order[0].toFixed(1)}</td><td className="n">{fmt(...r.total_cost, 0)}</td>
              <td className={'n ' + (r.pct_vs_nearest > 0 ? 'good' : r.pct_vs_nearest < 0 ? 'bad' : '')}>{r.method === 'nearest' ? 'baseline' : r.pct_vs_nearest.toFixed(1) + '%'}</td>
              <td className="n">{r.method === 'nearest' ? '' : r.better_runs + '/' + r.runs}</td></tr>)}</tbody></table>
          <p className="note">{R.orders} orders over 30 days, {R.total_units} stock units at the start. Total cost is km driven, plus {A.lost_order_km} km for each unserved order, plus {A.expired_unit_km} km for each expired unit. These weights are assumptions. Minutes use {A.speed_kmh} km/h and a {A.max_km} km limit. Distances are direct, not full routes. Stock is not replenished during the replay.</p></div>
        <div className="grid3"><div className="card"><h3>Total cost</h3>{bar('total_cost')}</div><div className="card"><h3>Units expired</h3>{bar('expired')}</div><div className="card"><h3>Unserved orders</h3>{bar('unserved')}</div></div>
      </>}
    </>
  );
}
