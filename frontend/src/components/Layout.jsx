import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { NAV_ITEMS } from '../constants'
import api from '../api'

function Sidebar() {
  const { user, loading, login, logout } = useAuth()
  const [syncing, setSyncing] = useState(false)

  const handleSync = async () => {
    setSyncing(true)
    try {
      const { data: trigger } = await api.post('/sync')
      if (trigger.status === 'cooldown' || trigger.status === 'already_in_progress') {
        await new Promise(r => setTimeout(r, 500))
        setSyncing(false)
        return
      }
      while (true) {
        await new Promise(r => setTimeout(r, 1000))
        const { data } = await api.get('/sync/status')
        if (!data.in_progress) break
      }
    } catch (err) {
      console.error('Sync error:', err)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <aside className="fixed top-0 left-0 h-screen w-16 bg-space-gray border-r border-cyber-blue/10 flex flex-col items-center py-6 z-40">
      <nav role="navigation" aria-label="Основная навигация" className="flex flex-col gap-2 w-full px-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            aria-label={item.label}
            title={item.label}
            className={({ isActive }) =>
              `flex items-center justify-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/30'
                  : 'text-gray-400 hover:text-cyber-blue hover:bg-space-gray-light border border-transparent'
              }`
            }
          >
            <span className="text-lg" aria-hidden="true">{item.icon}</span>
            <span className="hidden text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto px-2 w-full flex flex-col items-center gap-2">
        {loading ? (
          <span className="text-xs text-gray-500 font-mono animate-pulse">...</span>
        ) : user ? (
          <>
            <button
              onClick={handleSync}
              title="Обновить"
              className="w-10 h-10 flex items-center justify-center text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors text-lg"
            >
              <span className={`inline-block ${syncing ? 'animate-spin' : ''}`}>↻</span>
            </button>
            <button
              onClick={logout}
              title="Выйти"
              className="w-10 h-10 flex items-center justify-center text-crimson-alert border border-crimson-alert/30 rounded-lg hover:bg-crimson-alert/10 transition-colors text-lg"
            >
              ⏻
            </button>
          </>
        ) : (
          <button
            onClick={login}
            title="Войти"
            className="w-10 h-10 flex items-center justify-center text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors text-lg"
          >
            →
          </button>
        )}
      </div>
    </aside>
  )
}

export default function Layout({ children }) {
  return (
    <div className="h-screen overflow-hidden bg-space-black">
      <Sidebar />
      <main role="main" aria-label="Основной контент" className="ml-16 h-full overflow-y-auto p-4 flex flex-col">
        {children}
      </main>
    </div>
  )
}
