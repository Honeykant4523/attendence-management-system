import { ArrowRight, CheckCircle2, LockKeyhole, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { readableError } from '../services/api'

export default function LoginPage() {
  const { user, login } = useAuth(); const [form, setForm] = useState({ email: '', password: '' }); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  if (user) return <Navigate to="/" replace />
  const submit = async (event) => { event.preventDefault(); setBusy(true); setError(''); try { await login(form.email, form.password) } catch (err) { setError(readableError(err)) } finally { setBusy(false) } }
  return <div className="login-page"><section className="login-pitch"><div className="brand light"><div className="brand-mark">S</div><div>Smart<span>Attend</span></div></div><div><p className="eyebrow">ATTENDANCE, SIMPLIFIED</p><h1>Make every workday visible.</h1><p>One secure workspace for time, teams, leave and useful attendance insights.</p></div><ul><li><CheckCircle2 /> Role-aware HR operations</li><li><CheckCircle2 /> Privacy-conscious biometric flow</li><li><CheckCircle2 /> Live, exportable reporting</li></ul><div className="orb orb-one" /><div className="orb orb-two" /></section><section className="login-form-wrap"><form className="login-form" onSubmit={submit}><div className="login-icon"><ShieldCheck /></div><p className="eyebrow">WELCOME BACK</p><h2>Sign in to SmartAttend</h2><p className="muted">Use your organization account to continue.</p>{error && <div className="alert error">{error}</div>}<label>Work email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="you@company.com" /></label><label>Password<input type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder="Your password" /></label><button className="primary-button" disabled={busy}>{busy ? 'Signing in…' : <>Sign in <ArrowRight size={18} /></>}</button><p className="login-foot"><LockKeyhole size={14} /> Protected with token-based authentication</p></form></section></div>
}
