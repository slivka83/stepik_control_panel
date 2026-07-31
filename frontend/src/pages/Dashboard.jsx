import { useSync } from '../contexts/SyncContext'
import KpiCard from '../components/KpiCard'
import RevenueChart from '../components/RevenueChart'
import SubmissionsChart from '../components/SubmissionsChart'
import StudentsBar from '../components/StudentsBar'
import ErrorBanner from '../components/ErrorBanner'

export default function Dashboard() {
  const { data, loading, error, refresh } = useSync()
  const { kpi, cohorts, revenue, submissions } = data

  if (loading) {
    return (
      <div className="flex flex-col flex-1 gap-4 min-h-0">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={`skeleton-kpi-${i}`} className="glass-panel p-4 animate-pulse">
              <div className="h-3 bg-gray-700 rounded w-20 mb-2"></div>
              <div className="h-6 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={`skeleton-kpi-1-${i}`} className="glass-panel p-4 animate-pulse">
              <div className="h-3 bg-gray-700 rounded w-20 mb-2"></div>
              <div className="h-6 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
        <div className="glass-panel p-4 animate-pulse" style={{ height: '7rem' }}>
          <div className="h-3 bg-gray-700 rounded w-28 mb-2"></div>
          <div className="h-5 bg-gray-700 rounded w-full"></div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
          <div className="glass-panel p-4 animate-pulse flex flex-col">
            <div className="h-3 bg-gray-700 rounded w-32 mb-3"></div>
            <div className="flex-1 bg-gray-700 rounded min-h-0"></div>
          </div>
          <div className="glass-panel p-4 animate-pulse flex flex-col">
            <div className="h-3 bg-gray-700 rounded w-32 mb-3"></div>
            <div className="flex-1 bg-gray-700 rounded min-h-0"></div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">

      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard title="Доход /месяц" value={kpi?.total_revenue || 0} trend={kpi?.revenue_change_pct} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Покупки /месяц" value={kpi?.current_month_payments || 0} trend={kpi?.payments_change_pct} color="white" />
        <KpiCard title="Возвраты /месяц" value={kpi?.current_month_refunds_count || 0} trend={kpi?.refunds_change_pct} trendInverted color="white" suffix={'\u200A₽'} />
        <KpiCard title="Курсы" value={kpi?.courses_published || 0} secondValue={kpi?.courses_unpublished || 0} color="white" />
        <KpiCard title="Студенты" value={kpi?.students_prev_months ?? 0} secondValue={kpi?.current_month_students || 0} trend={kpi?.students_change_pct} secondHighlight color="white" />
        <KpiCard title="Средний рейтинг курсов" value={kpi?.average_rating || 0} ratingColor fractionDigits={2} minimumFractionDigits={2} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard title="Решения /месяц" value={kpi?.current_month_submissions || 0} trend={kpi?.submissions_change_pct} color="white" />
        <KpiCard title="Публичные решения" value={kpi?.published_solutions_prev_months ?? 0} secondValue={kpi?.published_solutions_current_month || 0} trend={kpi?.published_solutions_change_pct} secondHighlight color="white" />
        <KpiCard title="Комментарии" value={kpi?.comments_prev_months ?? 0} secondValue={kpi?.current_month_comments || 0} trend={kpi?.comments_change_pct} secondHighlight color="white" />
        <KpiCard title="Сертификаты" value={kpi?.certificates_prev_months ?? 0} secondValue={kpi?.certificates_current_month || 0} trend={kpi?.certificates_change_pct} secondHighlight color="white" />
        <KpiCard title="Отзывы" value={kpi?.reviews_prev_months ?? 0} secondValue={kpi?.reviews_current_month || 0} trend={kpi?.reviews_change_pct} secondHighlight color="white" />
        <KpiCard title="Средняя оценка шагов" value={kpi?.steps_average_grade || 0} ratingColor fractionDigits={2} minimumFractionDigits={2} />
      </div>

      <StudentsBar data={cohorts} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
        <RevenueChart data={revenue.months} />
        <SubmissionsChart data={submissions || {}} />
      </div>
    </div>
  )
}
