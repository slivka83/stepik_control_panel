import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useSync } from '../contexts/SyncContext'
import { STATUS_LABELS, STATUS_COLORS } from '../constants'
import { formatCurrency } from '../utils/formatNumber'
import ErrorBanner from '../components/ErrorBanner'
import { pluralize } from '../utils/pluralize'

const PAGE_SIZE = 20
const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'promo', label: 'По промокодам' },
  { key: 'recent', label: 'Последние операции' },
]

export default function Financials() {
  const { data, loading, error, refresh } = useSync()
  const financials = data.financials
  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months')
  const [paymentsPage, setPaymentsPage] = useState(1)

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

  const { summary, months, courses, promos, recent_payments } = financials || {}
  const hasData = (summary?.total_payments || 0) > 0

  const totalPages = Math.ceil((recent_payments?.length || 0) / PAGE_SIZE)
  const paginatedPayments = (recent_payments || []).slice(
    (paymentsPage - 1) * PAGE_SIZE,
    paymentsPage * PAGE_SIZE,
  )

  return (
    <div className="space-y-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="glass-panel p-3">
          <div className="text-gray-400 text-xs mb-1">Оборот</div>
          <div className="font-mono text-lg font-bold text-white">{formatCurrency(summary?.total_turnover)}</div>
        </div>
        <div className="glass-panel p-3">
          <div className="text-gray-400 text-xs mb-1">Доход</div>
          <div className="font-mono text-lg font-bold text-neon-green">{formatCurrency(summary?.total_income)}</div>
        </div>
        <div className="glass-panel p-3">
          <div className="text-gray-400 text-xs mb-1">Возвраты</div>
          <div className="font-mono text-lg font-bold text-crimson-alert">{formatCurrency(summary?.total_refunds)}</div>
        </div>
        <div className="glass-panel p-3">
          <div className="text-gray-400 text-xs mb-1">Чистый доход</div>
          <div className="font-mono text-lg font-bold text-cyber-blue">{formatCurrency(summary?.net_income)}</div>
        </div>
        <div className="glass-panel p-3">
          <div className="text-gray-400 text-xs mb-1">Покупок</div>
          <div className="font-mono text-lg font-bold text-amber-alert">{summary?.total_payments || 0}</div>
        </div>
      </div>

      {!hasData && (
        <div className="glass-panel p-4">
          <p className="text-gray-400 text-sm">Финансовые данные пока недоступны.</p>
        </div>
      )}

      {hasData && (
        <>
          <div className="flex gap-2 border-b border-gray-700 pb-0">
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
            <div className="glass-panel p-4">
              <h3 className="text-white font-medium mb-3">Доход по месяцам</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal">Месяц</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Возвраты</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...months].reverse().map((m) => (
                      <tr key={`month-${m.year}-${m.month_num}`} className="border-b border-gray-800">
                        <td className="py-2 text-white">{m.month}</td>
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
            </div>
          )}

          {activeTab === 'courses' && (
            <div className="glass-panel p-4">
              <h3 className="text-white font-medium mb-3">Доход по курсам</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal">Курс</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Возвраты</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courses.map((c) => (
                      <tr key={`course-${c.course_id}`} className="border-b border-gray-800">
                        <td className="py-2 text-white max-w-xs truncate" title={c.title}>{c.title}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{c.payments}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(c.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(c.income)}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {c.refunds > 0 ? `-${formatCurrency(c.refunds)}` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'promo' && (
            <div className="glass-panel p-4">
              <h3 className="text-white font-medium mb-3">Доход по промокодам</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal">Промокод</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Покупок</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Оборот</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Доход</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Возвраты</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Последнее применение</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(promos || []).map((p) => (
                      <tr key={`promo-${p.promo_code}`} className="border-b border-gray-800">
                        <td className="py-2 text-white font-mono">{p.promo_code}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{p.payments}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(p.turnover)}</td>
                        <td className="py-2 text-right font-mono text-neon-green">{formatCurrency(p.income)}</td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {p.refunds > 0 ? `-${formatCurrency(p.refunds)}` : '—'}
                        </td>
                        <td className="py-2 text-right text-gray-400">
                          {p.last_used ? new Date(p.last_used).toLocaleDateString('ru-RU') : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'recent' && (
            <div className="glass-panel p-4">
              <h3 className="text-white font-medium mb-3">
                Последние операции ({recent_payments.length} {pluralize(recent_payments.length, ['операция', 'операции', 'операций'])})
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-gray-400 py-2 font-normal">Дата</th>
                      <th className="text-left text-gray-400 py-2 font-normal">Курс</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Сумма покупки</th>
                      <th className="text-right text-gray-400 py-2 font-normal">Ваш доход</th>
                      <th className="text-center text-gray-400 py-2 font-normal">Статус</th>
                      <th className="text-center text-gray-400 py-2 font-normal">Промокод</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paginatedPayments.map((p) => (
                      <tr key={`payment-${p.id}`} className="border-b border-gray-800">
                        <td className="py-2 text-gray-300">{new Date(p.time).toLocaleDateString('ru-RU')}</td>
                        <td className="py-2 text-white max-w-xs truncate" title={p.course}>{p.course}</td>
                        <td className="py-2 text-right font-mono text-white">{formatCurrency(p.payment_amount)}</td>
                        <td className={`py-2 text-right font-mono ${p.status === 'refunded' ? 'text-crimson-alert' : 'text-neon-green'}`}>
                          {p.status === 'refunded' ? '−' : ''}{formatCurrency(p.amount)}
                        </td>
                        <td className={`py-2 text-center text-sm font-medium ${STATUS_COLORS[p.status] || 'text-gray-400'}`}>
                          {STATUS_LABELS[p.status] || p.status}
                        </td>
                        <td className="py-2 text-center text-gray-500 text-sm">{p.promo_code || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <span className="text-xs text-gray-500">
                    Страница {paymentsPage} из {totalPages}
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPaymentsPage((p) => Math.max(1, p - 1))}
                      disabled={paymentsPage === 1}
                      className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
                    >
                      ← Назад
                    </button>
                    <button
                      onClick={() => setPaymentsPage((p) => Math.min(totalPages, p + 1))}
                      disabled={paymentsPage === totalPages}
                      className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
                    >
                      Вперёд →
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
