import { BarChart3, Bot, CalendarDays, ClipboardCheck, FileBarChart, LayoutDashboard, LogOut, Menu, Moon, Settings, Sun, Users, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import ChatPanel from '../components/ChatPanel'
import { useAuth } from '../context/AuthContext'

const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/attendance', label: 'My attendance', icon: ClipboardCheck },
  { to: '/leaves', label: 'Leave centre', icon: CalendarDays },
  { to: '/reports', label: 'Reports', icon: FileBarChart },
  { to: '/profile', label: 'Profile & support', icon: Settings },
]

export default function AppLayout() {
  const { user, employee, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [dark, setDark] = useState(localStorage.getItem('smartattend_theme') === 'dark')
  const isAdmin = user.role !== 'employee'
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('smartattend_theme', dark ? 'dark' : 'light') }, [dark])
  const nav = [...navigation]
  if (isAdmin) nav.splice(1, 0, { to: '/employees', label: 'People', icon: Users }, { to: '/insights', label: 'AI insights', icon: BarChart3 })
  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? 'open' : ''}`}>
      <div className="brand"><div className="brand-mark">S</div><div>Smart<span>Attend</span><small>HR operations suite</small></div><button className="mobile-only icon-button" onClick={() => setMobileOpen(false)}><X /></button></div>
      <nav>{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setMobileOpen(false)}><Icon size={18} /> {label}</NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="employee-mini"><span>{employee?.firstName?.[0]}{employee?.lastName?.[0]}</span><div><b>{employee?.fullName}</b><small>{user.role.replace('_', ' ')}</small></div></div><button className="logout" onClick={logout}><LogOut size={17} /> Sign out</button></div>
    </aside>
    {mobileOpen && <button className="overlay" onClick={() => setMobileOpen(false)} aria-label="Close navigation" />}
    <main><header className="topbar"><button className="mobile-only icon-button" onClick={() => setMobileOpen(true)}><Menu /></button><div className="topbar-greeting"><span>Workspace</span><b>{new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })}</b></div><div className="topbar-actions"><button className="icon-button" onClick={() => setDark((value) => !value)} aria-label="Toggle theme">{dark ? <Sun size={18} /> : <Moon size={18} />}</button><button className="chat-trigger" onClick={() => setChatOpen(true)}><Bot size={18} /> Ask SmartAssist</button></div></header><div className="page-content"><Outlet /></div></main>
    {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
  </div>
}
