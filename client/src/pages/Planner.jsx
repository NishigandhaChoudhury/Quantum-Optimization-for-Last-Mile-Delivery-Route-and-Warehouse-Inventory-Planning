import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Chip } from '../ui.jsx';

export default function Planner() {
  const [pending, setPending] = useState([]);
  const [sel, setSel] = useState([]);
  const [res, setRes] = useState(null);
  const [method, setMethod] = useState('fefo');
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');
  const [busy, setBusy] = useState(false);
  const load = () => api('/orders?status=pending&limit=30').then((r) => setPending(r.items)).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);
  const toggle = (id) => { setRes(null); setSel((s) => s.includes(id) ? s.filter((x) => x !== id) : s.length < 4 ? [...s, id] : s); };
  const plan = async () => {
    setErr(''); setOk(''); setBusy(true);
    try { setRes(await api('/plan', { body: { orderIds: sel } })); } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const dispatch = async () => {
    setErr(''); setBusy(true);
    try {
      const r = await api('/dispatch', { body: { orderIds: sel, plan: res.plans[method].plan, method } });
      setOk(`Dispatched ${r.dispatched} order(s) using "${res.plans[method].label}". Stock updated.${r.unserved ? ` ${r.unserved} order(s) could not be served and stay pending.` : ''}`);
      setRes(null); setSel([]); load();
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const products = res ? [...new Set(res.shelf.map((s) => s.product))] : [];
  const minShelf = (p) => Math.min(...res.orders.filter((o) => o.product === p).map((o) => o.minShelfDays));
  return (
    <>
      <h2>Planner</h2>
      <p className="sub">Pick up to four pending orders, compare how each method assigns them, then dispatch with the one you choose.</p>
      <div className="card scroll"><h3>Pending orders ({sel.length} of 4 selected)</h3>
        <table><thead><tr><th></th><th>Order</th><th>Product</th><th className="n">Min days</th><th className="n">Km A</th><th className="n">Km B</th><th className="n">Km C</th></tr></thead>
          <tbody>{pending.map((o) => <tr key={o._id}><td><input type="checkbox" checked={sel.includes(o.orderId)} onChange={() => toggle(o.orderId)} aria-label={'Select ' + o.orderId} /></td>
            <td>{o.orderId.slice(0, 12)}</td><td>{o.product}</td><td className="n">{o.minShelfDays}</td><td className="n">{o.dist.A}</td><td className="n">{o.dist.B}</td><td className="n">{o.dist.C}</td></tr>)}</tbody></table>
        {!pending.length && <div className="empty">No pending orders. Add some on the Orders page.</div>}
        <div className="row" style={{ marginTop: 12 }}><button className="act" disabled={!sel.length || busy} onClick={plan}>Plan deliveries</button></div>
        <div className="err">{err}</div><div className="ok">{ok}</div>
      </div>
      {res && <>
        {products.map((p) => <div className="card" key={p}><h3>Shelf life of {p} per warehouse</h3>
          {res.shelf.filter((s) => s.product === p).map((s) => (
            <div className="strip" key={s.wid}><div><Chip w={s.wid} /> {s.units} units, {s.days} days</div>
              <div className="track"><div className="fill" style={{ width: Math.min(100, s.days / 2) + '%', background: s.days < 30 ? 'var(--amber)' : 'var(--green)' }} />
                <div className="mark" style={{ left: Math.min(100, minShelf(p) / 2) + '%' }} title="Shelf life the orders need" /></div></div>))}
          <p className="note">Full bar width is 200 days. The dark line is the shelf life your orders need.</p></div>)}
        <div className="card scroll"><h3>Choose a method and dispatch</h3>
          <table><thead><tr><th></th><th>Method</th>{res.orders.map((o, i) => <th key={o.orderId}>Order {i + 1}</th>)}<th className="n">Total km</th><th className="n">Unserved</th><th className="n">Avg days left on shipped stock</th></tr></thead>
            <tbody>{Object.entries(res.plans).map(([k, p]) => <tr key={k}>
              <td><input type="radio" name="m" checked={method === k} onChange={() => setMethod(k)} aria-label={p.label} /></td><td>{p.label}</td>
              {p.plan.map((w, i) => <td key={i}><Chip w={w} /></td>)}<td className="n">{p.km}</td><td className="n">{p.unserved}</td><td className="n">{p.avg_days_left ?? 'none'}</td></tr>)}</tbody></table>
          <p className="note">A lower number of days left means older stock goes out first. Expiry-aware methods may add a little distance to do that.</p>
          <div className="row" style={{ marginTop: 12 }}><button className="act" disabled={busy} onClick={dispatch}>Dispatch with {res.plans[method].label}</button></div>
        </div></>}
    </>
  );
}
