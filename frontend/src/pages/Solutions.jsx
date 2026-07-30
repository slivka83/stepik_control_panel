import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSync } from '../contexts/SyncContext'
import KpiCard from '../components/KpiCard'
import ErrorBanner from '../components/ErrorBanner'
import api from '../api'

const ROW_HEIGHT = 35
const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'hardest', label: 'Самые сложные' },
]

function Pagination({ page, totalPages, setPage }) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center justify-between mt-4 shrink-0">
      <span className="text-xs text-gray-500">
        Страница {page} из {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          ← Назад
        </button>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          Вперёд →
        </button>
      </div>
    </div>
  )
}

export default function Solutions() {
  const { data, loading, error, refresh } = useSync()
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months')
  const [page, setPage] = useState(1)
  const [rowsPerPage, setRowsPerPage] = useState(10)
  const tableRef = useRef(null)
  const prevRows = useRef(0)
  const resizeRef = useRef(null)

  useLayoutEffect(() => {
    const node = tableRef.current
    if (!node) return
    const header = node.querySelector('thead')
    const headerH = header?.offsetHeight || 0
    const avail = node.clientHeight - headerH - 4
    const calc = Math.max(1, Math.floor(avail / ROW_HEIGHT))
    if (calc !== prevRows.current) {
      prevRows.current = calc
      setRowsPerPage(calc)
    }
  })

  useEffect(() => {
    setPage(1)
    prevRows.current = 0
    const node = tableRef.current
    if (!node) return
    const ro = new ResizeObserver(() => {
      const header = node.querySelector('thead')
      const headerH = header?.offsetHeight || 0
      const avail = node.clientHeight - headerH - 4
      const calc = Math.max(1, Math.floor(avail / ROW_HEIGHT))
      if (calc !== prevRows.current) {
        prevRows.current = calc
        setRowsPerPage(calc)
      }
    })
    resizeRef.current = ro
    ro.observe(node)
    return () => ro.disconnect()
  }, [activeTab])

  const handleTabChange = (tab) => {
    setActiveTab(tab)
    setSearchParams({ tab })
  }

  const submissions = data.submissions || {}
  const months = submissions.months || []
  const byCourse = submissions.by_course || []

  const [hardestSteps, setHardestSteps] = useState([])
  const [hardestLoading, setHardestLoading] = useState(false)

  useEffect(() => {
    if (activeTab !== 'hardest') return
    setHardestLoading(true)
    api.get('/dashboard/hardest-steps?limit=200&min_submissions=1')
      .then((res) => setHardestSteps(res.data.steps || []))
      .catch(() => {})
      .finally(() => setHardestLoading(false))
  }, [activeTab])

  const totalSubmissions = months.reduce((s, m) => s + (m.total || 0), 0)
  const totalCorrect = months.reduce((s, m) => s + (m.correct || 0), 0)
  const avgSuccess = totalSubmissions > 0 ? Math.round((totalCorrect / totalSubmissions) * 100) : 0
  const lastMonth = months[months.length - 1]
  const lastSuccess = lastMonth && lastMonth.total > 0
    ? Math.round(((lastMonth.correct || 0) / lastMonth.total) * 100)
    : 0

  const hasData = totalSubmissions > 0

  const reversedMonths = [...months].reverse()
  const monthsTotalPages = Math.ceil(reversedMonths.length / rowsPerPage)
  const paginatedMonths = reversedMonths.slice((page - 1) * rowsPerPage, page * rowsPerPage)

  const coursesTotalPages = Math.ceil(byCourse.length / rowsPerPage)
  const paginatedCourses = byCourse.slice((page - 1) * rowsPerPage, page * rowsPerPage)

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={`skeleton-sol-${i}`} className="glass-panel p-3 animate-pulse">
              <div className="h-2 bg-gray-700 rounded w-16 mb-1"></div>
              <div className="h-5 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        <KpiCard title="Всего решений" value={totalSubmissions} color="white" />
        <KpiCard title="Правильных" value={totalCorrect} color="neon-green" />
        <KpiCard title="Средний успех" value={avgSuccess} suffix="%" color="cyber-blue" />
        <KpiCard title="Успех в последнем" value={lastSuccess} suffix="%" color={lastSuccess >= 50 ? 'neon-green' : 'amber-alert'} />
      </div>

      {!hasData && (
        <div className="glass-panel p-4 shrink-0">
          <p className="text-gray-400 text-sm">Данные о решениях отсутствуют. Запустите синхронизацию.</p>
        </div>
      )}

      {hasData && (
        <>
          <div className="flex gap-2 border-b border-gray-700 pb-0 shrink-0">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => handleTabChange(tab.key)}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === tab.key
                    ? 'border-cyber-blue text-cyber-blue'
                    : 'border-transparent text-gray-400 hover:text-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === 'months' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal w-[28%]">Месяц</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[16%]">Всего</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[20%]">Правильно</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[18%]">Неверно</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[18%]">Успех</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedMonths.map((m) => {
                      const wrong = (m.total || 0) - (m.correct || 0)
                      const pct = m.total > 0 ? ((m.correct || 0) / m.total * 100) : 0
                      return (
                        <tr key={m.month} className="border-b border-gray-800">
                          <td className="text-white font-mono text-xs truncate">{m.month}</td>
                          <td className="text-right text-gray-300 font-mono">{(m.total || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right text-neon-green font-mono">{(m.correct || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right text-crimson-alert font-mono">{wrong.toLocaleString('ru-RU')}</td>
                          <td className="text-right font-mono" style={{ color: pct >= 50 ? '#4ade80' : '#f59e0b' }}>{pct.toFixed(1)}%</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={monthsTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'courses' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal w-[38%]">Курс</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Всего</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[18%]">Правильно</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[16%]">Неверно</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Успех</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCourses.map((c) => {
                      const wrong = (c.total || 0) - (c.correct || 0)
                      const pct = c.total > 0 ? ((c.correct || 0) / c.total * 100) : 0
                      return (
                        <tr key={c.course_id} className="border-b border-gray-800">
                          <td className="text-white truncate" title={c.title}>{c.title}</td>
                          <td className="text-right text-gray-300 font-mono">{(c.total || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right text-neon-green font-mono">{(c.correct || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right text-crimson-alert font-mono">{wrong.toLocaleString('ru-RU')}</td>
                          <td className="text-right font-mono" style={{ color: pct >= 50 ? '#4ade80' : '#f59e0b' }}>{pct.toFixed(1)}%</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={coursesTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'hardest' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">
              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                {hardestLoading ? (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">Загрузка...</div>
                ) : hardestSteps.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">Нет данных</div>
                ) : (
                  <table className="w-full text-sm table-fixed fin-table">
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left text-gray-400 py-2 font-normal w-[12%]">Step ID</th>
                        <th className="text-left text-gray-400 py-2 font-normal w-[34%]">Курс</th>
                        <th className="text-right text-gray-400 py-2 font-normal w-[12%]">Всего</th>
                        <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Правильно</th>
                        <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Неверно</th>
                        <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Успех</th>
                      </tr>
                    </thead>
                    <tbody>
                      {hardestSteps.map((s) => (
                        <tr key={s.stepik_step_id} className="border-b border-gray-800">
                          <td className="text-cyber-blue font-mono text-xs">{s.stepik_step_id}</td>
                          <td className="text-white truncate text-xs" title={s.course_title}>{s.course_title}</td>
                          <td className="text-right text-gray-300 font-mono text-xs">{(s.total || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right text-neon-green font-mono text-xs">{(s.correct || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right text-crimson-alert font-mono text-xs">{(s.wrong || 0).toLocaleString('ru-RU')}</td>
                          <td className="text-right font-mono text-xs font-bold" style={{ color: s.success_pct >= 50 ? '#4ade80' : '#f43f5e' }}>{s.success_pct}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
