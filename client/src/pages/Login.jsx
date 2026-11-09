import { useState } from 'react';
import { api } from '../api.js';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('planner@demo.com');
  const [password, setPassword] = useState('planner123');
  const [err, setErr] = useState('');
  const go = async () => {
    setErr('');
    try { const r = await api('/auth/login', { body: { email, password } }); localStorage.setItem('token', r.token); onLogin(r.user); }
    catch (e) { setErr(e.message); }
  };
  return (
    <div className="login"><div className="card">
      <h2>Sign in</h2><p className="sub">Expiry-aware warehouse planner</p>
      <div className="row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
        <label>Email<input value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && go()} /></label>
      </div>
      <button className="act" onClick={go}>Sign in</button>
      <div className="err">{err}</div>
      <p className="note">Demo accounts: planner@demo.com / planner123, admin@demo.com / admin123.</p>
    </div></div>
  );
}
