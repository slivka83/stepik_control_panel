import { useSync } from '../contexts/SyncContext'
import ErrorBanner from '../components/ErrorBanner'
import StudentsBar from '../components/StudentsBar'

const COHORT_COLORS = {
  Active: '#4ade80',
  Passive: '#38bdf8',
  Fading: '#f59e0b',
  Sleeping: '#f43f5e',
  Zombie: '#a855f7',
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function Students() {
  const { data, loading, error, refresh } = useSync()
  const cohorts = data.cohorts
  const students = data.students?.students || []
  const total = data.students?.total || 0

  if (loading) {
    return (
      <div className="flex flex-col flex-1 gap-4 min-h-0">
        <div className="glass-panel p-4 animate-pulse" style={{ height: '7.25rem' }}>
          <div className="h-3 bg-gray-700 rounded w-28 mb-2"></div>
          <div className="h-5 bg-gray-700 rounded w-full"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <StudentsBar data={cohorts} />

      <div className="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">
            Список студентов
          </h2>
          <span className="text-xs text-gray-500">
            {total} всего
          </span>
        </div>
        <div className="overflow-auto flex-1 min-h-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 text-xs uppercase tracking-wider border-b border-space-gray/50">
                <th className="pb-2 pr-2 font-medium">ID</th>
                <th className="pb-2 pr-2 font-medium">Курс</th>
                <th className="pb-2 pr-2 font-medium">Статус</th>
                <th className="pb-2 pr-2 font-medium text-right">Баллы</th>
                <th className="pb-2 pr-2 font-medium text-center">Сертификат</th>
                <th className="pb-2 pr-2 font-medium">Присоединился</th>
                <th className="pb-2 font-medium">Активность</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={`${s.course_id}-${s.student_id}`} className="border-b border-space-gray/30 hover:bg-space-gray/40 transition-colors">
                  <td className="py-2 pr-2 text-cyber-blue font-mono text-xs">{s.student_id}</td>
                  <td className="py-2 pr-2 text-gray-300 max-w-[200px] truncate" title={s.course_title}>{s.course_title}</td>
                  <td className="py-2 pr-2">
                    <span
                      className="inline-block px-2 py-0.5 rounded text-xs font-medium"
                      style={{
                        backgroundColor: `${COHORT_COLORS[s.cohort_status] || '#6b7280'}20`,
                        color: COHORT_COLORS[s.cohort_status] || '#6b7280',
                      }}
                    >
                      {s.cohort_status}
                    </span>
                  </td>
                  <td className="py-2 pr-2 text-right font-mono text-xs text-gray-300">{s.points_earned}</td>
                  <td className="py-2 pr-2 text-center">
                    {s.certificate_issued
                      ? <span className="text-neon-green text-xs font-medium">Да</span>
                      : <span className="text-gray-500 text-xs">—</span>
                    }
                  </td>
                  <td className="py-2 pr-2 text-xs text-gray-400 whitespace-nowrap">{formatDate(s.date_joined)}</td>
                  <td className="py-2 text-xs text-gray-400 whitespace-nowrap">{formatDate(s.last_viewed_at)}</td>
                </tr>
              ))}
              {students.length === 0 && (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-gray-500 text-sm">
                    Нет данных о студентах
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
