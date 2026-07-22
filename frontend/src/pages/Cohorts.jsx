import { useSync } from '../contexts/SyncContext'
import { COHORT_COLORS, COHORT_LABELS, COHORT_DAYS } from '../constants'
import ErrorBanner from '../components/ErrorBanner'
import { pluralize } from '../utils/pluralize'

export default function Cohorts() {
  const { data, loading, error, refresh } = useSync()
  const cohorts = data.cohorts

  const total = Object.values(cohorts).reduce((sum, val) => sum + (val || 0), 0)

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-bold text-white">Когортный анализ</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={`skeleton-cohort-${i}`} className="glass-panel p-4 animate-pulse">
              <div className="h-3 bg-gray-700 rounded w-20 mb-2"></div>
              <div className="h-6 bg-gray-700 rounded w-16 mb-2"></div>
              <div className="h-2 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-white">Когортный анализ</h1>
        <span className="text-xs text-gray-500 font-mono">
          Всего: {total} {pluralize(total, ['студент', 'студента', 'студентов'])}
        </span>
      </div>

      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {Object.keys(COHORT_LABELS).map((key) => {
          const value = cohorts[key] || 0
          const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0
          const colors = COHORT_COLORS[key]
          return (
            <div key={key} className="glass-panel glass-panel-hover p-4 transition-all duration-300">
              <div className="flex items-center gap-2 mb-2">
                <span className={colors.text}>●</span>
                <span className="text-gray-400 text-sm">{COHORT_LABELS[key]}</span>
              </div>
              <div className={`font-mono text-2xl font-bold ${colors.text}`}>{value}</div>
              <div className="mt-1 text-xs text-gray-500 font-mono">
                {COHORT_DAYS[key]} · {percentage}%
              </div>
              <div className="mt-2 w-full bg-gray-700 rounded-full h-1.5">
                <div className={`h-1.5 rounded-full ${colors.bg}`} style={{ width: `${percentage}%` }}></div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="glass-panel p-4">
        <h3 className="text-white font-medium mb-3">Определение когорт</h3>
        <div className="text-sm text-gray-400 space-y-2">
          <p>Когортный статус определяется на основе даты последней активности студента:</p>
          <ul className="list-disc list-inside space-y-1 ml-4">
            <li><span className="text-neon-green font-mono">Active</span> — последняя активность ≤ 7 дней назад</li>
            <li><span className="text-cyber-blue font-mono">Passive</span> — последняя активность 8–30 дней назад</li>
            <li><span className="text-amber-alert font-mono">Fading</span> — последняя активность 30–90 дней назад</li>
            <li><span className="text-crimson-alert font-mono">Sleeping</span> — последняя активность {'>'} 90 дней назад</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
