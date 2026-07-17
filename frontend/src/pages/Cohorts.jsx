import { useSync } from '../contexts/SyncContext'
import { COHORT_COLORS, COHORT_LABELS, COHORT_DAYS } from '../constants'

export default function Cohorts() {
  const { data, loading } = useSync()
  const cohorts = data.cohorts

  const total = Object.values(cohorts).reduce((sum, val) => sum + val, 0)

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Когортный анализ</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="glass-panel p-5 animate-pulse">
              <div className="h-4 bg-gray-700 rounded w-20 mb-3"></div>
              <div className="h-8 bg-gray-700 rounded w-16 mb-2"></div>
              <div className="h-3 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Когортный анализ</h1>
        <span className="text-xs text-gray-500 font-mono">Всего: {total} студентов</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {Object.keys(COHORT_LABELS).map((key) => {
          const value = cohorts[key] || 0
          const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0
          const colors = COHORT_COLORS[key]
          return (
            <div key={key} className="glass-panel glass-panel-hover p-5 transition-all duration-300">
              <div className="flex items-center gap-2 mb-3">
                <span className={colors.text}>●</span>
                <span className="text-gray-400 text-sm">{COHORT_LABELS[key]}</span>
              </div>
              <div className={`font-mono text-3xl font-bold ${colors.text}`}>
                {value}
              </div>
              <div className="mt-2 text-xs text-gray-500 font-mono">
                {COHORT_DAYS[key]} · {percentage}%
              </div>
              <div className="mt-3 w-full bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${colors.bg}`}
                  style={{ width: `${percentage}%` }}
                ></div>
              </div>
            </div>
          )
        })}
      </div>

      <div className="glass-panel p-6">
        <h3 className="text-white font-medium mb-4">Определение когорт</h3>
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
