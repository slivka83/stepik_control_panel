import { useState, useEffect, useRef } from 'react'
import api from '../api'
import { useSync } from '../contexts/SyncContext'
import { getCached, setCached } from '../cache'

const COHORT_COLORS = {
  active: { text: 'text-neon-green', bg: 'bg-neon-green' },
  passive: { text: 'text-cyber-blue', bg: 'bg-cyber-blue' },
  fading: { text: 'text-amber-alert', bg: 'bg-amber-alert' },
  sleeping: { text: 'text-crimson-alert', bg: 'bg-crimson-alert' },
}

const COHORT_LABELS = {
  active: 'Активные',
  passive: 'Пассивные',
  fading: 'Затухающие',
  sleeping: 'Спящие',
}

const COHORT_DAYS = {
  active: '≤ 7 дней',
  passive: '8–30 дней',
  fading: '30–90 дней',
  sleeping: '> 90 дней',
}

export default function Cohorts() {
  const [cohorts, setCohorts] = useState(getCached('cohorts') || {})
  const loaded = useRef(!!getCached('cohorts'))
  const { refreshKey } = useSync()

  useEffect(() => {
    const fetchCohorts = async () => {
      try {
        const res = await api.get('/api/dashboard/cohorts')
        setCohorts(res.data)
        setCached('cohorts', res.data)
      } catch (err) {
        console.error('Cohorts fetch error:', err)
      }
      loaded.current = true
    }
    fetchCohorts()
  }, [refreshKey])

  if (!loaded.current) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyber-blue font-mono animate-pulse">Загрузка данных...</div>
      </div>
    )
  }

  const total = Object.values(cohorts).reduce((sum, val) => sum + val, 0)

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

      <div className="glass-panel p-6">
        <h3 className="text-white font-medium mb-4">Predictive Churn</h3>
        <div className="p-4 bg-amber-alert/10 border border-amber-alert/20 rounded-lg">
          <div className="flex items-start gap-3">
            <span className="text-amber-alert text-lg">⚠</span>
            <div>
              <p className="text-sm text-gray-300 mb-2">
                ML-модель выявляет студентов с высоким риском оттока на основе:
              </p>
              <ul className="text-xs text-gray-400 space-y-1 ml-4 list-disc list-inside">
                <li>Увеличение пауз между уроками в 2+ раза</li>
                <li>Доля ошибок time_limit_exceeded {'>'} 15% за последние 5 попыток</li>
                <li>Статус когорты "Active" при указанных паттернах</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
