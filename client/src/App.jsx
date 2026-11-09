import { useEffect, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes, Navigate } from 'react-router-dom';
import { api, getToken } from './api.js';
import Login from './pages/Login.jsx';
import Overview from './pages/Overview.jsx';
import Orders from './pages/Orders.jsx';
import Planner from './pages/Planner.jsx';
import Stock from './pages/Stock.jsx';
import Benchmark from './pages/Benchmark.jsx';
import Lab from './pages/Lab.jsx';

export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const out = () => setUser(null);
    window.addEventListener('logout', out);
    if (!getToken()) setReady(true);
    else api('/auth/me').then((r) => setUser(r.user)).catch(() => {}).finally(() => setReady(true));
    return () => window.removeEventListener('logout', out);
  }, []);
  if (!ready) return null;
  if (!user) return <Login onLogin={setUser} />;
  const logout = () => { localStorage.removeItem('token'); setUser(null); };
  return (
    <BrowserRouter>
      <div className="shell">
        <nav>
          <h1>Expiry-aware warehouse planner</h1>
          <p>Decide which warehouse ships each order.</p>
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/orders">Orders</NavLink>
          <NavLink to="/planner">Planner</NavLink>
          <NavLink to="/stock">Stock</NavLink>
          <NavLink to="/benchmark">Benchmark</NavLink>
          <NavLink to="/lab">Quantum lab</NavLink>
          <div className="who">{user.name} ({user.role})<br /><button onClick={logout}>Sign out</button></div>
        </nav>
        <main>
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/orders" element={<Orders />} />
            <Route path="/planner" element={<Planner />} />
            <Route path="/stock" element={<Stock user={user} />} />
            <Route path="/benchmark" element={<Benchmark />} />
            <Route path="/lab" element={<Lab />} />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
