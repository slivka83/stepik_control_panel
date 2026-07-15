import { NavLink } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const navItems = [
  { to: '/', label: 'Дашборд', icon: '◈' },
  { to: '/courses', label: 'Курсы', icon: '◆' },
  { to: '/financials', label: 'Финансы', icon: '◉' },
  { to: '/cohorts', label: 'Когорты', icon: '◎' },
]

export default function Layout({ children }) {
  const { user, loading, login, logout } = useAuth()

  return (
    <div className="flex min-h-screen bg-space-black">
      <aside className="w-16 lg:w-56 bg-space-gray border-r border-cyber-blue/10 flex flex-col items-center lg:items-start py-6">
        <div className="mb-8 px-2">
          <h1 className="text-cyber-blue font-mono text-sm lg:text-lg font-bold neon-text hidden lg:block">
            STEPIK CONTROL
          </h1>
          <div className="text-cyber-blue text-xl lg:hidden text-center">◈</div>
        </div>

        <nav className="flex flex-col gap-2 w-full px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg transition-all duration-200 ${
                  isActive
                    ? 'bg-cyber-blue/20 text-cyber-blue border border-cyber-blue/30'
                    : 'text-gray-400 hover:text-cyber-blue hover:bg-space-gray-light border border-transparent'
                }`
              }
            >
              <span className="text-lg">{item.icon}</span>
              <span className="hidden lg:block text-sm font-medium">{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto px-2 hidden lg:block">
          <div className="glass-panel p-3 text-xs text-gray-500">
            <div className="text-cyber-blue font-mono">v0.1.0</div>
            <div className="mt-1">Read-Only Mode</div>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <header className="h-14 bg-space-gray/50 border-b border-cyber-blue/10 flex items-center px-6 backdrop-blur-sm">
          <h2 className="text-white font-medium">Stepik Control Panel</h2>
          <div className="ml-auto flex items-center gap-4">
            {loading ? (
              <span className="text-xs text-gray-500 font-mono animate-pulse">...</span>
            ) : user ? (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-neon-green animate-pulse"></div>
                  <span className="text-xs text-gray-400 font-mono">SYNCED</span>
                </div>
                <span className="text-xs text-gray-500 font-mono">ID: {user.stepik_id}</span>
                <button
                  onClick={logout}
                  className="px-3 py-1 text-xs text-crimson-alert border border-crimson-alert/30 rounded-lg hover:bg-crimson-alert/10 transition-colors"
                >
                  Выйти
                </button>
              </div>
            ) : (
              <button
                onClick={login}
                className="px-4 py-1.5 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors font-medium"
              >
                Войти через Stepik
              </button>
            )}
          </div>
        </header>

        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
