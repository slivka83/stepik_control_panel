export default function ErrorBanner({ message, onRetry }) {
  return (
    <div className="glass-panel p-4 border border-crimson-alert/30 bg-crimson-alert/5">
      <div className="flex items-center gap-3">
        <span className="text-crimson-alert text-lg">✕</span>
        <div className="flex-1">
          <p className="text-crimson-alert text-sm font-medium">Ошибка загрузки данных</p>
          <p className="text-gray-400 text-xs mt-1">{message}</p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg hover:bg-cyber-blue/10 transition-colors"
          >
            Повторить
          </button>
        )}
      </div>
    </div>
  );
}
