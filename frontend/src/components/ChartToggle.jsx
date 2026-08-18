function ChartIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="w-4 h-4"
    >
      <line x1="12" y1="20" x2="12" y2="10" />
      <line x1="18" y1="20" x2="18" y2="4" />
      <line x1="6" y1="20" x2="6" y2="16" />
    </svg>
  );
}

function TableIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="w-4 h-4"
    >
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="21" y2="15" />
      <line x1="12" y1="9" x2="12" y2="21" />
    </svg>
  );
}

export default function ChartToggle({ visible, viewMode, onToggle, metric, onMetricChange, metrics }) {
  if (!visible) return null;
  return (
    <div className="flex items-center gap-2">
      {viewMode === 'chart' && (
        <select
          value={metric}
          onChange={(e) => onMetricChange(e.target.value)}
          aria-label="Метрика графика"
          className="bg-space-gray border border-gray-700 rounded px-2 py-1 text-sm text-white"
        >
          {Object.entries(metrics).map(([key, m]) => (
            <option key={key} value={key}>
              {m.label}
            </option>
          ))}
        </select>
      )}
      <button
        type="button"
        onClick={onToggle}
        aria-pressed={viewMode === 'chart'}
        title={viewMode === 'chart' ? 'Показать таблицу' : 'Показать график'}
        aria-label={viewMode === 'chart' ? 'Показать таблицу' : 'Показать график'}
        className={`p-1 rounded transition-colors ${
          viewMode === 'chart'
            ? 'text-cyber-blue'
            : 'text-white hover:text-cyber-blue hover:drop-shadow-[0_0_4px_rgba(56,189,248,0.8)]'
        }`}
      >
        {viewMode === 'chart' ? <TableIcon /> : <ChartIcon />}
      </button>
    </div>
  );
}
