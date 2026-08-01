import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSync } from '../contexts/SyncContext'
import { formatCurrency } from '../utils/formatNumber'
import ErrorBanner from '../components/ErrorBanner'
import KpiCard from '../components/KpiCard'
import { pluralize } from '../utils/pluralize'

const ROW_HEIGHT = 35
const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'promo', label: 'По промокодам' },
  { key: 'utms', label: 'По UTM' },
  { key: 'recent', label: 'Последние операции' },
]

function formatUtmTooltip(raw) {
  const utm = raw?.last_course_click_utm
  if (!utm || typeof utm !== 'object') return ''
  return Object.entries(utm)
    .map(([k, v]) => `${k}: ${v ?? ''}`)
    .join('\n')
}

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

export default function Financials() {
  const { data, loading, error, refresh } = useSync()
  const financials = data.financials
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

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={`skeleton-fin-${i}`} className="glass-panel p-3 animate-pulse">
              <div className="h-2 bg-gray-700 rounded w-16 mb-1"></div>
              <div className="h-5 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!financials) {
    return (
      <div className="space-y-4">
        {error && <ErrorBanner message={error} onRetry={refresh} />}
        <div className="glass-panel p-8 text-center">
          <p className="text-gray-400">Финансовые данные пока недоступны</p>
        </div>
      </div>
    )
  }

  const { summary, months, years, courses, promos, utms, recent_payments } = financials || {}
  const hasData = (summary?.total_payments || 0) > 0

  const reversedMonths = [...(months || [])].reverse()
  const monthsTotalPages = Math.ceil(reversedMonths.length / rowsPerPage)
  const paginatedMonths = reversedMonths.slice((page - 1) * rowsPerPage, page * rowsPerPage)

  const reversedYears = [...(years || [])].reverse()
  const yearsTotalPages = Math.ceil(reversedYears.length / rowsPerPage)
  const paginatedYears = reversedYears.slice((page - 1) * rowsPerPage, page * rowsPerPage)

  const coursesTotalPages = Math.ceil((courses || []).length / rowsPerPage)
  const paginatedCourses = (courses || []).slice((page - 1) * rowsPerPage, page * rowsPerPage)

  const promosTotalPages = Math.ceil((promos || []).length / rowsPerPage)
  const paginatedPromos = (promos || []).slice((page - 1) * rowsPerPage, page * rowsPerPage)

  const utmsTotalPages = Math.ceil((utms || []).length / rowsPerPage)
  const paginatedUtms = (utms || []).slice((page - 1) * rowsPerPage, page * rowsPerPage)

  const paymentsTotalPages = Math.ceil((recent_payments?.length || 0) / rowsPerPage)
  const paginatedPayments = (recent_payments || []).slice(
    (page - 1) * rowsPerPage,
    page * rowsPerPage,
  )

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 shrink-0">
        <KpiCard title="Оборот" value={summary?.total_turnover || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Доход" value={summary?.total_income || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Возвраты" value={summary?.total_refunds || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Чистый доход" value={summary?.net_income || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Покупок" value={summary?.total_payments || 0} color="white" />
      </div>

      {!hasData && (
        <div className="glass-panel p-4 shrink-0">
          <p className="text-gray-400 text-sm">Финансовые данные пока недоступны.</p>
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
                      <th className="text-right text-gray-400 py-2 font-normal w-[16%]">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[22%]">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[20%]">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Возвраты</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedMonths.map((m) => (
                      <tr key={`month-${m.year}-${m.month_num}`} className="border-b border-gray-800">
                        <td className="py-2 text-white truncate">{m.month}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{m.payments_count}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(m.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(m.income)}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {m.refunds > 0 ? `-${formatCurrency(m.refunds)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={monthsTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'years' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal w-[28%]">Год</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[16%]">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[22%]">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[20%]">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Возвраты</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedYears.map((m) => (
                      <tr key={`year-${m.year}`} className="border-b border-gray-800">
                        <td className="py-2 text-white font-mono truncate">{m.year}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{m.payments_count}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(m.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(m.income)}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {m.refunds > 0 ? `-${formatCurrency(m.refunds)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={yearsTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'courses' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal w-[32%]">Курс</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[12%]">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Стоимость</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Возвраты</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedCourses.map((c) => (
                      <tr key={`course-${c.course_id}`} className="border-b border-gray-800">
                        <td className="py-2 text-white truncate" title={c.title}>{c.title}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{c.payments}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(c.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(c.income)}</td>
                        <td className="py-2 text-right font-mono text-white">{c.price ? formatCurrency(c.price) : '—'}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {c.refunds > 0 ? `-${formatCurrency(c.refunds)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={coursesTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'promo' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal w-[18%]">Промокод</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[12%]">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[18%]">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[16%]">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Возвраты</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[22%]">Последнее применение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedPromos.map((p) => (
                      <tr key={`promo-${p.promo_code}`} className="border-b border-gray-800">
                        <td className="py-2 text-white font-mono truncate">{p.promo_code}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{p.payments}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(p.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(p.income)}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {p.refunds > 0 ? `-${formatCurrency(p.refunds)}` : '—'}
                        </td>
                        <td className="py-2 text-right text-gray-400 truncate">
                          {p.last_used ? new Date(p.last_used).toLocaleDateString('ru-RU') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={promosTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'utms' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal w-[18%]">UTM</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[12%]">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[18%]">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[16%]">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[14%]">Возвраты</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[22%]">Последнее применение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedUtms.map((u) => (
                      <tr key={`utm-${u.utm_source}`} className="border-b border-gray-800">
                        <td className="py-2 text-white truncate">{u.utm_source}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{u.payments}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(u.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(u.income)}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {u.refunds > 0 ? `-${formatCurrency(u.refunds)}` : '—'}
                        </td>
                        <td className="py-2 text-right text-gray-400 truncate">
                          {u.last_used ? new Date(u.last_used).toLocaleDateString('ru-RU') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={utmsTotalPages} setPage={setPage} />
            </div>
          )}

          {activeTab === 'recent' && (
            <div className="glass-panel p-4 flex flex-col flex-1 min-h-0">

              <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
                <table className="w-full text-sm table-fixed fin-table">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal pr-4 w-[12%]">Дата</th>
                      <th className="text-left text-gray-400 py-2 font-normal pr-4">Курс</th>
                      <th className="text-right text-gray-400 py-2 font-normal pr-4 w-[14%]">Студент</th>
                      <th className="text-right text-gray-400 py-2 font-normal pr-4 w-[8%]">Оплата</th>
                      <th className="text-right text-gray-400 py-2 font-normal pr-4 w-[8%]">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal pr-4 w-[6%]">Канал</th>
                      <th className="text-right text-gray-400 py-2 font-normal pr-4 w-[12%]">Промокод</th>
                      <th className="text-right text-gray-400 py-2 font-normal pr-4 w-[4%]">Подарок</th>
                      <th className="text-right text-gray-400 py-2 font-normal w-[10%]">UTM</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedPayments.map((p) => (
                      <tr key={`payment-${p.id}`} className="border-b border-gray-800">
                        <td className="py-2 text-gray-300 truncate pr-4">
                          {`${new Date(p.time).toLocaleDateString('ru-RU')} ${new Date(p.time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`}
                        </td>
                        <td className="py-2 text-white truncate pr-4" title={p.course}>{p.course}</td>
                        <td className="py-2 text-right text-gray-300 truncate pr-4" title={p.student || ''}>{p.student || '—'}</td>
                        <td className="py-2 text-right font-mono text-white truncate pr-4">{formatCurrency(p.payment_amount)}</td>
                        <td className={`py-2 text-right font-mono truncate pr-4 ${p.status === 'refunded' ? 'text-crimson-alert line-through' : 'text-neon-green'}`}>
                          {formatCurrency(p.amount)}
                        </td>
                        <td className="py-2 text-right text-gray-500 text-sm truncate pr-4">{p.channel || '—'}</td>
                        <td className="py-2 text-right text-gray-500 text-sm truncate pr-4">{p.promo_code || '—'}</td>
                        <td className="py-2 text-right text-gray-500 text-sm truncate pr-4">{p.is_gift ? 'Да' : '—'}</td>
                        <td className="py-2 text-right text-gray-500 text-sm truncate" title={formatUtmTooltip(p.raw)}>
                          {p.utm_source_label || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination page={page} totalPages={paymentsTotalPages} setPage={setPage} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
