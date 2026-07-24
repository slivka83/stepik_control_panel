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
      await api.post('/sync')
    } catch (err) {
      console.error('Sync error:', err)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <aside className="fixed top-0 left-0 h-screen w-16 lg:w-56 bg-space-gray border-r border-cyber-blue/10 flex flex-col items-center lg:items-start py-6 z-40">
      <nav role="navigation" aria-label="Основная навигация" className="flex flex-col gap-2 w-full px-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            aria-label={item.label}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 ${
                isActive
                  ? 'bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/30'
                  : 'text-gray-400 hover:text-cyber-blue hover:bg-space-gray-light border border-transparent'
              }`
            }
          >
            <span className="text-lg" aria-hidden="true">{item.icon}</span>
            <span className="hidden lg:block text-sm font-medium">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto px-2 w-full">
        {loading ? (
          <span className="text-xs text-gray-500 font-mono animate-pulse">...</span>
        ) : user ? (
          <div className="flex flex-col gap-2">
            <button
              onClick={handleSync}
              className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors font-medium text-left"
            >
              Обновить
            </button>
            <button
              onClick={logout}
              className="px-2 py-1 text-xs text-crimson-alert border border-crimson-alert/30 rounded-lg hover:bg-crimson-alert/10 transition-colors"
            >
              Выйти
            </button>
          </div>
        ) : (
          <button
            onClick={login}
            className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors font-medium w-full text-left"
          >
            Войти
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
      <main role="main" aria-label="Основной контент" className="ml-16 lg:ml-56 h-full overflow-y-auto p-4 flex flex-col">
        {children}
      </main>
    </div>
  )
}
