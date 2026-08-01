import { memo, useState } from 'react'
import { useSync } from '../contexts/SyncContext'
import ErrorBanner from '../components/ErrorBanner'
import KpiCard from '../components/KpiCard'
import { STEPIK_URLS } from '../constants.jsx'

const SORT_COLUMNS = {
  title: { numeric: false },
  status: { numeric: false },
  enrollment_count: { numeric: true },
  submissions_total: { numeric: true },
  comments_count: { numeric: true },
  reviews_count: { numeric: true },
  average_rating: { numeric: true },
  price: { numeric: true, nullLast: true },
  income: { numeric: true, nullLast: true },
  published_at: { numeric: false, nullLast: true },
}

const compareCourses = (a, b, key, dir) => {
  const cfg = SORT_COLUMNS[key]
  const va = a[key]
  const vb = b[key]
  if (cfg.nullLast) {
    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1
  }
  let diff
  if (cfg.numeric) {
    diff = (va ?? 0) - (vb ?? 0)
  } else {
    diff = String(va ?? '').toLowerCase().localeCompare(String(vb ?? '').toLowerCase(), 'ru')
  }
  return dir === 'asc' ? diff : -diff
}

const SortableTh = memo(function SortableTh({ label, sortKey, sort, onSort, align = 'left' }) {
  const active = sort.key === sortKey
  const arrow = (
    <span className={`shrink-0 ${active ? 'text-cyber-blue' : 'invisible'}`}>
      {sort.dir === 'asc' ? '↑' : '↓'}
    </span>
  )
  return (
    <th
      className={`pb-2 pr-3 font-medium cursor-pointer select-none hover:text-gray-300 transition-colors ${align === 'right' ? 'text-right' : ''}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {align === 'right' && arrow}
        <span>{label}</span>
        {align === 'left' && arrow}
      </span>
    </th>
  )
})

function getRatingColor(rating) {
  const r = Math.max(1, Math.min(5, rating))
  const stops = [
    [1.0, 239, 68, 68],
    [2.0, 249, 115, 22],
    [3.0, 234, 179, 8],
    [4.0, 132, 204, 22],
    [4.5, 100, 214, 81],
    [4.9, 74, 222, 128],
  ]
  let i = 0
  while (i < stops.length - 1 && stops[i + 1][0] < r) i++
  if (i >= stops.length - 1) {
    const [, cr, cg, cb] = stops[stops.length - 1]
    return `rgb(${cr}, ${cg}, ${cb})`
  }
  const [r0, r1, g1, b1] = stops[i]
  const [r1v, r2, g2, b2] = stops[i + 1]
  const t = (r - r0) / (r1v - r0)
  return `rgb(${Math.round(r1 + (r2 - r1) * t)}, ${Math.round(g1 + (g2 - g1) * t)}, ${Math.round(b1 + (b2 - b1) * t)})`
}

function pctStr(total, correct) {
  if (!total) return '—'
  return `${Math.round((correct / total) * 100)}%`
}

const RatingCell = memo(function RatingCell({ rating }) {
  if (!rating) return <span className="text-gray-500">—</span>
  return <span className="font-mono font-bold" style={{ color: getRatingColor(rating) }}>{rating.toFixed(2)}</span>
})

function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const dd = String(d.getDate()).padStart(2, '0')
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const yyyy = d.getFullYear()
  return `${dd}.${mm}.${yyyy}`
}

const CourseRow = memo(function CourseRow({ course }) {
  const isPublished = course.status?.toLowerCase() === 'published'
  const totalSubs = course.submissions_total || 0
  const correctSubs = course.submissions_correct || 0
  const price = course.price
  return (
    <tr className="border-b border-space-gray/30 hover:bg-space-gray/40 transition-colors">
      <td className="py-2.5 pr-3">
        <a
          href={STEPIK_URLS.course(course.stepik_course_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyber-blue text-sm font-medium hover:underline truncate block"
          title={course.title}
        >
          {course.title}
        </a>
      </td>
      <td className="py-2.5 pr-3 text-right">
        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
          isPublished
            ? 'bg-neon-green/20 text-neon-green'
            : 'bg-gray-500/20 text-gray-400'
        }`}>
          {isPublished ? 'Опубликован' : 'Черновик'}
        </span>
      </td>
      <td className="py-2.5 pr-3 font-mono text-sm text-gray-300 text-right">{course.enrollment_count || 0}</td>
      <td className="py-2.5 pr-3 font-mono text-sm text-gray-300 text-right">
        {totalSubs > 0 ? `${totalSubs} (${pctStr(totalSubs, correctSubs)})` : '—'}
      </td>
      <td className="py-2.5 pr-3 font-mono text-sm text-gray-300 text-right">{course.comments_count || 0}</td>
      <td className="py-2.5 pr-3 font-mono text-sm text-gray-300 text-right">{course.reviews_count || 0}</td>
      <td className="py-2.5 pr-3 text-right"><RatingCell rating={course.average_rating} /></td>
      <td className="py-2.5 pr-3 font-mono text-sm text-right">
        {price != null ? `${price.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
      <td className="py-2.5 pr-3 font-mono text-sm text-right text-neon-green">
        {course.income != null ? `${course.income.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
      <td className="py-2.5 pr-3 font-mono text-xs text-gray-400 text-right truncate">{fmtDate(course.published_at)}</td>
    </tr>
  )
})

export default function Courses() {
  const { data, loading, error, refresh } = useSync()
  const courses = data.courses || []
  const kpi = data.kpi || {}
  const [sort, setSort] = useState({ key: 'published_at', dir: 'desc' })

  const onSort = (key) => {
    setSort(s => s.key === key
      ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: SORT_COLUMNS[key].numeric ? 'desc' : 'asc' })
  }

  const sortedCourses = [...courses].sort((a, b) => compareCourses(a, b, sort.key, sort.dir))

  if (loading) {
    return (
    <div className="flex flex-col flex-1 gap-4 min-h-0 min-w-0">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={`sk-${i}`} className="glass-panel p-4 animate-pulse">
              <div className="h-3 bg-gray-700 rounded w-20 mb-2"></div>
              <div className="h-6 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
        <div className="glass-panel p-4 animate-pulse flex-1">
          <div className="h-3 bg-gray-700 rounded w-28 mb-3"></div>
          <div className="h-5 bg-gray-700 rounded w-full"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
        <KpiCard title="Всего курсов" value={kpi?.courses_count || 0} color="white" />
        <KpiCard title="Опубликовано" value={kpi?.courses_published || 0} color="white" />
        <KpiCard title="Черновиков" value={kpi?.courses_unpublished || 0} color="white" />
        <KpiCard title="Всего студентов" value={kpi?.total_students || 0} color="white" />
        <KpiCard title="Средний рейтинг" value={kpi?.average_rating || 0} ratingColor fractionDigits={2} minimumFractionDigits={2} />
      </div>

      {courses.length === 0 ? (
        <div className="glass-panel p-8 text-center">
          <div className="text-3xl mb-3">◆</div>
          <h3 className="text-white text-lg mb-2">Нет курсов</h3>
          <p className="text-gray-400 text-sm">
            Подключите аккаунт Stepik для импорта курсов
          </p>
          <a
            href="/api/auth/login"
            className="inline-block mt-4 px-6 py-2 bg-cyber-blue/20 text-cyber-blue rounded-lg border border-cyber-blue/30 hover:bg-cyber-blue/30 transition-colors text-sm font-medium"
          >
            Подключить Stepik
          </a>
        </div>
      ) : (
        <div className="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="overflow-x-hidden overflow-y-auto flex-1 min-h-0">
            <table className="w-full table-fixed text-sm">
              <colgroup>
                <col style={{ width: '25%' }} />
                <col style={{ width: '9%' }} />
                <col style={{ width: '7%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '9%' }} />
                <col style={{ width: '6%' }} />
                <col style={{ width: '7%' }} />
                <col style={{ width: '8%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '9%' }} />
              </colgroup>
              <thead>
                <tr className="text-left text-gray-500 text-xs uppercase border-b border-space-gray/50">
                  <SortableTh label="Название" sortKey="title" sort={sort} onSort={onSort} />
                  <SortableTh label="Статус" sortKey="status" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Студенты" sortKey="enrollment_count" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Решения" sortKey="submissions_total" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Комментарии" sortKey="comments_count" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Отзывы" sortKey="reviews_count" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Рейтинг" sortKey="average_rating" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Стоимость" sortKey="price" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Доход" sortKey="income" sort={sort} onSort={onSort} align="right" />
                  <SortableTh label="Опубликован" sortKey="published_at" sort={sort} onSort={onSort} align="right" />
                </tr>
              </thead>
              <tbody>
                {sortedCourses.map((course) => (
                  <CourseRow key={course.id} course={course} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
