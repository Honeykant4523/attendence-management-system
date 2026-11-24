import { Bot, Send, X } from 'lucide-react'
import { useState } from 'react'
import api, { readableError } from '../services/api'

export default function ChatPanel({ onClose }) {
  const [messages, setMessages] = useState([{ from: 'bot', text: 'Hi! Ask about your authorized attendance, leave balance, or reports.' }])
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const ask = async (event) => {
    event.preventDefault()
    if (!draft.trim() || sending) return
    const question = draft.trim(); setDraft(''); setMessages((old) => [...old, { from: 'user', text: question }]); setSending(true)
    try { const { data } = await api.post('/chat', { message: question }); setMessages((old) => [...old, { from: 'bot', text: data.answer }]) }
    catch (error) { setMessages((old) => [...old, { from: 'bot', text: readableError(error) }]) }
    finally { setSending(false) }
  }
  return <aside className="chat-panel"><header><span><Bot size={18} /> SmartAssist</span><button className="icon-button" onClick={onClose} aria-label="Close chat"><X size={18} /></button></header>
    <div className="chat-messages">{messages.map((item, index) => <p className={item.from} key={index}>{item.text}</p>)}</div>
    <form onSubmit={ask}><input value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Ask a question…" /><button aria-label="Send"><Send size={16} /></button></form>
  </aside>
}
