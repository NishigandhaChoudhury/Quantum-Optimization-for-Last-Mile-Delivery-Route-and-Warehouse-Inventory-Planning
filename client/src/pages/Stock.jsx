import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Chip, dayClass } from '../ui.jsx';

export default function Stock({ user }) {
  const [items, setItems] = useState([]);
  const [edit, setEdit] = useState({});
  const [msg, setMsg] = useState({ t: '', ok: false });
  const isAdmin = user.role === 'admin';
  const load = () => api('/stock').then((r) => setItems(r.items)).catch((e) => setMsg({ t: e.message, ok: false }));
  useEffect(() => { load(); }, []);
  const save = async (s) => {
    const e = edit[s.id] || {};
    try { await api('/stock/' + s.id, { method: 'PUT', body: { units: e.units ?? s.units, expiryDate: e.expiryDate ?? s.expiryDate } });
      setMsg({ t: `Saved ${s.product} in warehouse ${s.wid}.`, ok: true }); setEdit((x) => ({ ...x, [s.id]: undefined })); load(); }
    catch (er) { setMsg({ t: er.message, ok: false }); }
  };
  const reseed = async () => {
    if (!confirm('Reload warehouses, stock and orders from the CSV files? Dispatch history will be cleared.')) return;
    try { const r = await api('/admin/reseed', { method: 'POST', body: {} }); setMsg({ t: `Reloaded ${r.orders} orders and ${r.stock} stock lines.`, ok: true }); load(); }
    catch (er) { setMsg({ t: er.message, ok: false }); }
  };
  return (
    <>
      <h2>Stock</h2>
      <p className="sub">{isAdmin ? 'Edit units and expiry dates per warehouse and product.' : 'Stock per warehouse. Only admins can edit.'}</p>
      <div className="card scroll">
        <table><thead><tr><th>Warehouse</th><th>Product</th><th className="n">Units</th><th>Expiry date</th><th className="n">Days left</th>{isAdmin && <th></th>}</tr></thead>
          <tbody>{items.map((s) => { const e = edit[s.id] || {}; return (
            <tr key={s.id}><td><Chip w={s.wid} /></td><td>{s.product}</td>
              <td className="n">{isAdmin ? <input type="number" min="0" value={e.units ?? s.units} onChange={(ev) => setEdit({ ...edit, [s.id]: { ...e, units: ev.target.value } })} /> : s.units}</td>
              <td>{isAdmin ? <input type="date" value={(e.expiryDate ?? s.expiryDate).slice(0, 10)} onChange={(ev) => setEdit({ ...edit, [s.id]: { ...e, expiryDate: ev.target.value } })} /> : s.expiryDate.slice(0, 10)}</td>
              <td className={`n ${dayClass(s.daysLeft)}`}>{s.daysLeft}</td>
              {isAdmin && <td><button className="ghost" disabled={!edit[s.id]} onClick={() => save(s)}>Save</button></td>}</tr>); })}</tbody></table>
        <div className={msg.ok ? 'ok' : 'err'}>{msg.t}</div>
        {isAdmin && <div className="row"><button className="ghost" onClick={reseed}>Reload data from CSV files</button></div>}
      </div>
    </>
  );
}
