import { useSync } from '../contexts/SyncContext'
import ErrorBanner from '../components/ErrorBanner'
import StudentsBar from '../components/StudentsBar'
import SubmissionsChart from '../components/SubmissionsChart'
import ActiveStudentsChart from '../components/ActiveStudentsChart'

export default function Students() {
  const { data, loading, error, refresh } = useSync()
  const cohorts = data.cohorts
  const submissions = data.submissions
  const financials = data.financials
  const community = financials?.community || {}
  const commentsMonthly = community.comments_monthly || {}

  const commentsChartData = {
    months: Object.entries(commentsMonthly)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, val]) => {
        const [y, m] = key.split('-')
        const date = new Date(+y, +m - 1)
        const raw = date.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })
        const month = raw.charAt(0).toUpperCase() + raw.slice(1)
        return { month, total: val, correct: val }
      }),
  }

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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
        <ActiveStudentsChart data={data.activeStudents} hatched lightLabel="Уникальные студенты" tooltipRight />
        <ActiveStudentsChart data={data.publishedSolutions} title="Опубликованные решения" primaryColor="#a855f7" secondaryColor="#581c87" hatched hideLightLegend hideDarkLegend />
        <SubmissionsChart data={commentsChartData} title="Комментарии" primaryColor="#b8860b" secondaryColor="#6b4f0a" hideCorrectLegend hideTotalLegend tooltipRight />
        <SubmissionsChart data={submissions || {}} />
      </div>
    </div>
  )
}
