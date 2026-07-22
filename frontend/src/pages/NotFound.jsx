import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
      <div className="text-8xl font-bold text-cyber-blue mb-4">404</div>
      <h1 className="text-2xl font-semibold text-white mb-2">Страница не найдена</h1>
      <p className="text-gray-400 mb-8 max-w-md">
        Запрашиваемая страница не существует или была перемещена.
      </p>
      <Link
        to="/"
        className="px-6 py-3 bg-cyber-blue/20 border border-cyber-blue/40 rounded-lg text-cyber-blue hover:bg-cyber-blue/30 transition-colors"
      >
        Вернуться на дашборд
      </Link>
    </div>
  )
}
