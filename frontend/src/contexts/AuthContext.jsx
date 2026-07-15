import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext(null)
const TOKEN_KEY = 'stepik_session_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const sessionToken = params.get('session_token')
    if (sessionToken) {
      setToken(sessionToken)
      window.history.replaceState({}, '', window.location.pathname)
    }

    const token = getToken()
    if (!token) {
      setLoading(false)
      return
    }

    const checkAuth = async () => {
      try {
        const res = await fetch('/api/auth/me', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          setUser(await res.json())
        } else {
          clearToken()
          setUser(null)
        }
      } catch {
        clearToken()
        setUser(null)
      } finally {
        setLoading(false)
      }
    }
    checkAuth()
  }, [])

  const login = () => {
    window.location.href = '/api/auth/login'
  }

  const logout = () => {
    clearToken()
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
