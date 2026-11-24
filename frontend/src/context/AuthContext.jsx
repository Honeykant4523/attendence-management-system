import { createContext, useContext, useEffect, useState } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('smartattend_token')
    if (!token) { setLoading(false); return }
    api.get('/auth/me').then(({ data }) => setSession(data)).catch(() => localStorage.removeItem('smartattend_token')).finally(() => setLoading(false))
  }, [])

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('smartattend_token', data.accessToken)
    setSession({ user: data.user, employee: data.employee })
    return data
  }
  const logout = () => { localStorage.removeItem('smartattend_token'); setSession(null) }
  return <AuthContext.Provider value={{ ...session, loading, login, logout, refresh: async () => setSession((await api.get('/auth/me')).data) }}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
