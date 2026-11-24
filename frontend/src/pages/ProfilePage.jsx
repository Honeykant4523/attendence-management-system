import { BadgeHelp, Building2, Headphones, Mail, Phone, Save, ShieldCheck, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import api, { readableError } from '../services/api'

const supportPhone = '1800 123 2026'
const supportEmail = 'support@smartattend.example'

export default function ProfilePage() {
  const { employee, user, refresh } = useAuth()
  const [form, setForm] = useState({ firstName: '', lastName: '', email: '', phone: '' })
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setForm({ firstName: employee?.firstName || '', lastName: employee?.lastName || '', email: employee?.email || user?.email || '', phone: employee?.phone || '' })
  }, [employee, user])

  const saveProfile = async (event) => {
    event.preventDefault(); setError(''); setNotice('')
    try {
      await api.patch('/employees/me', form)
      await refresh()
      setNotice('Your profile has been updated.')
    } catch (err) { setError(readableError(err)) }
  }

  return <><section className="page-title"><div><p className="eyebrow">ACCOUNT CENTRE</p><h1>Profile & support</h1><p>Manage your contact information and get help whenever you need it.</p></div></section>{notice && <div className="alert success">{notice}</div>}{error && <div className="alert error">{error}</div>}<section className="profile-layout"><article className="panel profile-card"><div className="profile-avatar">{employee?.firstName?.[0]}{employee?.lastName?.[0]}</div><p className="eyebrow">SIGNED IN AS</p><h2>{employee?.fullName || 'SmartAttend user'}</h2><p className="profile-role">{user?.role?.replace('_', ' ')}</p><div className="profile-meta"><span><Building2 size={16} /> {employee?.department?.name || 'No department assigned'}</span><span><ShieldCheck size={16} /> ID: {employee?.employeeCode || '—'}</span></div></article><form className="panel profile-form" onSubmit={saveProfile}><div className="panel-title"><div><h2><UserRound size={18} /> Personal details</h2><p>Visible to authorized HR staff and administrators.</p></div></div><div className="form-grid"><Field label="First name" value={form.firstName} onChange={(firstName) => setForm({ ...form, firstName })} /><Field label="Last name" value={form.lastName} onChange={(lastName) => setForm({ ...form, lastName })} /><Field label="Email address" type="email" value={form.email} onChange={(email) => setForm({ ...form, email })} /><Field label="Phone number" type="tel" value={form.phone} onChange={(phone) => setForm({ ...form, phone })} /></div><button className="primary-button"><Save size={17} /> Save profile</button></form></section><section className="support-grid"><article className="panel support-card"><div className="support-icon"><Phone /></div><p className="eyebrow">HELP LINE</p><h2>Need immediate help?</h2><p>Call SmartAttend support for login, attendance, or account-access assistance.</p><a className="support-link" href={`tel:${supportPhone.replaceAll(' ', '')}`}>{supportPhone}</a><small>Available Monday–Friday, 9:00 AM–6:00 PM</small></article><article className="panel support-card"><div className="support-icon"><Mail /></div><p className="eyebrow">SUPPORT DESK</p><h2>Send a support request</h2><p>Contact the support team with screenshots or details of the issue you are facing.</p><a className="support-link" href={`mailto:${supportEmail}`}>{supportEmail}</a><small>We aim to reply within one business day.</small></article><article className="panel support-card"><div className="support-icon"><BadgeHelp /></div><p className="eyebrow">QUICK HELP</p><h2>Common questions</h2><p>For attendance, use My attendance. For leave, open Leave centre. Ask your HR team for account or policy help.</p><span className="support-note">Keep your password private.</span></article></section></>
}

function Field({ label, type = 'text', value, onChange }) { return <label>{label}<input required type={type} value={value} onChange={(event) => onChange(event.target.value)} /></label> }
