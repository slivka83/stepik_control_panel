import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useSync } from '../contexts/SyncContext'
import { NAV_ITEMS } from '../constants.jsx'
import api from '../api'

function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h} ч ${m} мин`
  if (m > 0) return `${m} мин ${sec} с`
  return `${sec} с`
}

function Sidebar() {
  const { user, loading, login, logout } = useAuth()
  const { syncStatus } = useSync()
  const [syncing, setSyncing] = useState(false)
  const [progress, setProgress] = useState(0)
  const startRef = useRef(null)
  const [now, setNow] = useState(Date.now())

  const isSyncing = syncing || syncStatus.in_progress
  const displayProgress = syncing ? progress : (syncStatus.progress || 0)

  useEffect(() => {
    if (!isSyncing) {
      startRef.current = null
      return
    }
    if (startRef.current === null) startRef.current = Date.now()
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [isSyncing])

  const buildSyncTooltip = () => {
    if (!isSyncing) return 'Обновить'
    const elapsed = startRef.current ? (now - startRef.current) / 1000 : 0
    const pct = displayProgress
    const remaining = pct > 0 ? (elapsed * (100 - pct)) / pct : null
    return [
      `Завершено: ${Math.round(pct)}%`,
      `Прошло: ${formatDuration(elapsed)}`,
      `Осталось: ${remaining !== null ? `~${formatDuration(remaining)}` : '…'}`,
    ].join('\n')
  }

  const handleSync = async () => {
    setSyncing(true)
    setProgress(0)
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
        setProgress(data.progress || 0)
        if (!data.in_progress) break
      }
    } catch (err) {
      console.error('Sync error:', err)
    } finally {
      setSyncing(false)
      setProgress(0)
    }
  }

  return (
    <aside className="fixed top-0 left-0 h-screen w-16 bg-space-gray border-r border-cyber-blue/10 flex flex-col items-center py-6 z-40">
      <nav role="navigation" aria-label="Основная навигация" className="flex flex-col w-full">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            aria-label={item.label}
            title={item.label}
            className={({ isActive }) =>
              `flex items-center justify-center gap-3 px-3 py-2.5 transition-all duration-200 border-l-2 ${
                isActive
                  ? 'text-cyber-blue border-l-cyber-blue bg-cyber-blue/10'
                  : 'text-gray-400 border-l-transparent hover:text-gray-200 hover:bg-white/5'
              }`
            }
          >
            <span
              className="text-lg"
              aria-hidden="true"
              style={item.iconScale ? { transform: `scale(${item.iconScale})`, display: 'inline-block' } : undefined}
            >
              {item.icon}
            </span>
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
              title={buildSyncTooltip()}
              className="relative w-10 h-10 flex items-center justify-center border border-cyber-blue/30 rounded-lg overflow-hidden text-lg group"
              disabled={isSyncing}
            >
              {isSyncing && (
                <span
                  className="absolute bottom-0 left-0 w-full bg-cyber-blue/25"
                  style={{ height: `${displayProgress}%`, transition: 'height 1.5s ease-out' }}
                />
              )}
              <span className={`relative z-10 inline-block text-cyber-blue transition-colors duration-300 ${isSyncing ? 'animate-spin' : 'group-hover:text-white'}`}>↻</span>
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
      <main role="main" aria-label="Основной контент" className="ml-16 h-full min-h-0 overflow-y-auto p-4 flex flex-col">
        {children}
      </main>
    </div>
  )
}
