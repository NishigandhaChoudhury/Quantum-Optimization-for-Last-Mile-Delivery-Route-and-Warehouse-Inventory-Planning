import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { Chip } from '../ui.jsx';

export default function Orders() {
  const [status, setStatus] = useState('pending');
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, limit: 25 });
  const [products, setProducts] = useState([]);
  const [form, setForm] = useState({ product: '', lat: '', lon: '', minShelfDays: 14 });
  const [msg, setMsg] = useState({ t: '', ok: false });
  const load = () => api(`/orders?status=${status}&page=${page}&limit=25`).then(setData).catch((e) => setMsg({ t: e.message, ok: false }));
  useEffect(() => { load(); }, [status, page]);
  useEffect(() => { api('/products').then((r) => { setProducts(r.products); setForm((f) => ({ ...f, product: r.products[0] || '' })); }); }, []);
  const create = async () => {
    try { const r = await api('/orders', { body: form }); setMsg({ t: `Order ${r.orderId} created. Distances: A ${r.dist.A} km, B ${r.dist.B} km, C ${r.dist.C} km.`, ok: true }); setStatus('pending'); setPage(1); load(); }
    catch (e) { setMsg({ t: e.message, ok: false }); }
  };
  const pages = Math.max(1, Math.ceil(data.total / data.limit));
  return (
    <>
      <h2>Orders</h2>
      <p className="sub">Add an order by drop location. Distances to each warehouse are calculated for you.</p>
      <div className="card"><h3>New order</h3>
        <div className="row">
          <label>Product<select value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })}>{products.map((p) => <option key={p}>{p}</option>)}</select></label>
          <label>Drop latitude<input value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} placeholder="26.91" /></label>
          <label>Drop longitude<input value={form.lon} onChange={(e) => setForm({ ...form, lon: e.target.value })} placeholder="75.79" /></label>
          <label>Min days of shelf life<input type="number" value={form.minShelfDays} onChange={(e) => setForm({ ...form, minShelfDays: e.target.value })} /></label>
          <button className="act" onClick={create}>Add order</button>
        </div>
        <div className={msg.ok ? 'ok' : 'err'}>{msg.t}</div>
      </div>
      <div className="card scroll">
        <div className="row"><label>Show<select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
          <option value="pending">Pending</option><option value="dispatched">Dispatched</option><option value="">All</option></select></label></div>
        <table><thead><tr><th>Order</th><th>Product</th><th className="n">Min days</th><th className="n">Km A</th><th className="n">Km B</th><th className="n">Km C</th><th>Status</th><th>Shipped from</th></tr></thead>
          <tbody>{data.items.map((o) => <tr key={o._id}><td>{o.orderId.slice(0, 12)}</td><td>{o.product}</td><td className="n">{o.minShelfDays}</td>
            <td className="n">{o.dist.A}</td><td className="n">{o.dist.B}</td><td className="n">{o.dist.C}</td><td>{o.status}</td><td>{o.assignedWid ? <Chip w={o.assignedWid} /> : ''}</td></tr>)}</tbody></table>
        {!data.items.length && <div className="empty">No orders here.</div>}
        <div className="pager"><button className="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page} of {pages} ({data.total} orders)</span>
          <button className="ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button></div>
      </div>
    </>
  );
}
