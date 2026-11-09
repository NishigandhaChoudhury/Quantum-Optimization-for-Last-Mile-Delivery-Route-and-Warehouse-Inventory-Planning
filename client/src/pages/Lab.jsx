import { useState } from 'react';
import { Bar } from 'react-chartjs-2';
import { api } from '../api.js';
import { Chip } from '../ui.jsx';

export default function Lab() {
  const [seed, setSeed] = useState(1);
  const [r, setR] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const run = async () => { setErr(''); setBusy(true); try { const x = await api('/quantum', { body: { seed } }); if (x.error) throw new Error(x.error); setR(x); } catch (e) { setErr(e.message); } setBusy(false); };
  const row = (n, x) => x ? <tr><td>{n}</td><td>{x.plan.map((w, i) => <Chip key={i} w={w} />)}</td><td className="n">{x.cost}</td><td className={'n ' + (x.gap_pct === 0 ? 'good' : 'bad')}>{x.gap_pct}%</td></tr>
    : <tr><td>{n}</td><td colSpan="3" className="bad">No valid plan found</td></tr>;
  return (
    <>
      <h2>Quantum lab</h2>
      <p className="sub">Solves one 4-order batch three ways on a simulated 12-qubit QAOA circuit and compares against the exact best answer.</p>
      <div className="card"><div className="row"><label>Batch number<input type="number" min="1" value={seed} onChange={(e) => setSeed(+e.target.value)} /></label>
        <button className="act" disabled={busy} onClick={run}>Run batch</button></div>
        <div className="err">{err}</div><div className="note">{busy ? 'Running the simulated circuit, this takes a few seconds.' : ''}</div></div>
      {r && <>
        <div className="card scroll"><h3>{r.product}: 4 orders, {r.qubits} qubits, {r.layers} layers, {r.shots} shots</h3>
          <table><thead><tr><th>Method</th><th>Warehouse per order</th><th className="n">Cost</th><th className="n">Gap to exact</th></tr></thead>
            <tbody>{row('Exact (checks every option)', r.exact)}{row('QAOA only (best valid sample)', r.qaoa)}{row('QAOA + repair + refine', r.hybrid)}</tbody></table>
          <p className="note">Only {(r.valid_rate * 100).toFixed(1)}% of QAOA samples were valid plans. Random guessing would give {(r.random_valid_rate * 100).toFixed(1)}%. With only 81 possible plans, 1024 samples find the best one easily, so a match here does not show a quantum advantage. Stock is capped at {r.stock_cap} units per product and warehouse so the orders compete. Took {r.seconds} s.</p></div>
        <div className="card"><h3>Ten most likely circuit outcomes</h3>
          <Bar data={{ labels: r.top.map((t) => t.bits), datasets: [{ data: r.top.map((t) => t.prob * 100), backgroundColor: r.top.map((t) => t.valid ? '#2e8b6a' : '#c4493d') }] }}
            options={{ plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => `${c.raw.toFixed(2)}%, ${r.top[c.dataIndex].valid ? 'valid plan, cost ' + r.top[c.dataIndex].cost : 'invalid plan'}` } } },
              scales: { y: { title: { display: true, text: 'Probability (%)' } }, x: { ticks: { font: { size: 10 } } } } }} />
          <p className="note">Green bars are valid plans, red bars break a rule.</p></div></>}
    </>
  );
}
