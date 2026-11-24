import { TrendingUp } from 'lucide-react'

export default function StatCard({ label, value, hint, icon: Icon, tone = 'blue' }) {
  return <article className={`stat-card ${tone}`}>
    <div><p>{label}</p><strong>{value}</strong>{hint && <small><TrendingUp size={13} /> {hint}</small>}</div>
    <span className="stat-icon"><Icon size={21} /></span>
  </article>
}
