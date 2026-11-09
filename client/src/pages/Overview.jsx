import { useEffect, useState } from 'react';
import { Scatter } from 'react-chartjs-2';
import { api } from '../api.js';
import { WCOL, dayClass } from '../ui.jsx';

export default function Overview() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState('');
  useEffect(() => { api('/overview').then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <div className="err">{err}</div>;
  if (!d) return <p>Loading</p>;
  const products = [...new Set(d.stock.map((s) => s.product))];
  const cell = (w, p) => { const s = d.stock.find((x) => x.wid === w && x.product === p);
    return s ? <span className={dayClass(s.daysLeft)}>{s.units} units, {s.daysLeft} days</span> : 'none'; };
  const I = d.impact;
  return (
    <>
      <h2>Overview</h2>
      <p className="sub">Live view of stock, orders and the effect of your dispatches.</p>
      <div className="grid4">
        <div className="card"><div className="kpi">{d.counts.pending}</div>pending orders</div>
        <div className="card"><div className="kpi">{d.counts.dispatched}</div>dispatched orders</div>
        <div className="card"><div className="kpi">{d.counts.units}</div>units in stock</div>
        <div className="card"><div className="kpi">{d.counts.expiringSoon}</div>units expiring within 30 days</div>
      </div>
      <div className="card"><h3>Effect of your dispatches</h3>
        {I.orders === 0 ? <div className="empty">No orders dispatched yet. Dispatch orders from the Planner to see the impact here.</div> :
          <p>{I.orders} orders dispatched. Distance driven: {I.km.toFixed(1)} km, against {I.kmNearest.toFixed(1)} km if every order had shipped from the nearest warehouse
            ({I.km >= I.kmNearest ? '+' : ''}{(I.km - I.kmNearest).toFixed(1)} km). Shipped stock had {I.avgDaysLeft?.toFixed(0)} days of shelf life left on average.</p>}
      </div>
      <div className="grid2">
        <div className="card"><h3>Warehouses and delivery points</h3>
          <Scatter data={{ datasets: [
            { label: 'Delivery drops', data: d.drops.map((x) => ({ x: x.lon, y: x.lat })), backgroundColor: '#9db5ba', pointRadius: 2 },
            ...d.warehouses.map((w) => ({ label: 'Warehouse ' + w.wid, data: [{ x: w.lon, y: w.lat }], backgroundColor: WCOL[w.wid], pointRadius: 9 }))] }}
            options={{ scales: { x: { title: { display: true, text: 'Longitude' } }, y: { title: { display: true, text: 'Latitude' } } } }} />
        </div>
        <div className="card scroll"><h3>Stock and days of shelf life left</h3>
          <table><thead><tr><th>Product</th>{['A', 'B', 'C'].map((w) => <th key={w}>{w}</th>)}</tr></thead>
            <tbody>{products.map((p) => <tr key={p}><td>{p}</td>{['A', 'B', 'C'].map((w) => <td key={w}>{cell(w, p)}</td>)}</tr>)}</tbody></table>
          <p className="note">Amber means 30 days or fewer. Stock updates every time you dispatch.</p>
        </div>
      </div>
    </>
  );
}
