import { useState } from 'react'
import { useSync } from '../contexts/SyncContext'
import { STATUS_LABELS, STATUS_COLORS } from '../constants'

export default function Financials() {
  const { data, loading } = useSync()
  const financials = data.financials
  const [activeTab, setActiveTab] = useState('months')

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Финансовая аналитика</h1>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass-panel p-5 animate-pulse">
              <div className="h-3 bg-gray-700 rounded w-16 mb-2"></div>
              <div className="h-6 bg-gray-700 rounded w-24"></div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  if (!financials) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Финансовая аналитика</h1>
        <div className="glass-panel p-12 text-center">
          <p className="text-gray-400">Финансовые данные пока недоступны</p>
        </div>
      </div>
    )
  }

  const { summary, months, courses, recent_payments } = financials || {}
  const hasData = (summary?.total_payments || 0) > 0

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Финансовая аналитика</h1>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="glass-panel p-5">
          <div className="text-gray-400 text-xs mb-1">Оборот</div>
          <div className="font-mono text-xl font-bold text-white">
            {(summary?.total_turnover || 0).toLocaleString('ru-RU')} ₽
          </div>
        </div>
        <div className="glass-panel p-5">
          <div className="text-gray-400 text-xs mb-1">Доход</div>
          <div className="font-mono text-xl font-bold text-neon-green">
            {(summary?.total_income || 0).toLocaleString('ru-RU')} ₽
          </div>
        </div>
        <div className="glass-panel p-5">
          <div className="text-gray-400 text-xs mb-1">Возвраты</div>
          <div className="font-mono text-xl font-bold text-crimson-alert">
            {(summary?.total_refunds || 0).toLocaleString('ru-RU')} ₽
          </div>
        </div>
        <div className="glass-panel p-5">
          <div className="text-gray-400 text-xs mb-1">Чистый доход</div>
          <div className="font-mono text-xl font-bold text-cyber-blue">
            {(summary?.net_income || 0).toLocaleString('ru-RU')} ₽
          </div>
        </div>
        <div className="glass-panel p-5">
          <div className="text-gray-400 text-xs mb-1">Покупок</div>
          <div className="font-mono text-xl font-bold text-amber-alert">
            {summary?.total_payments || 0}
          </div>
        </div>
      </div>

      {!hasData && (
        <div className="glass-panel p-6">
          <p className="text-gray-400 text-sm">
            Финансовые данные пока недоступны.
          </p>
        </div>
      )}

      {hasData && (
        <>
          <div className="flex gap-2 border-b border-gray-700 pb-0">
            {[
              { key: 'months', label: 'По месяцам' },
              { key: 'courses', label: 'По курсам' },
              { key: 'recent', label: 'Последние операции' },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
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
            <div className="glass-panel p-6">
              <h3 className="text-white font-medium mb-4">Доход по месяцам</h3>
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
                    {[...months].reverse().map((m, i) => (
                      <tr key={i} className="border-b border-gray-800">
                        <td className="py-2 text-white">{m.month}</td>
                        <td className="py-2 text-right font-mono text-gray-300">{m.payments_count}</td>
                        <td className="py-2 text-right font-mono text-white">
                          {m.turnover.toLocaleString('ru-RU')} ₽
                        </td>
                        <td className="py-2 text-right font-mono text-neon-green">
                          {m.income.toLocaleString('ru-RU')} ₽
                        </td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {m.refunds > 0 ? `-${m.refunds.toLocaleString('ru-RU')} ₽` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'courses' && (
            <div className="glass-panel p-6">
              <h3 className="text-white font-medium mb-4">Доход по курсам</h3>
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
                    {courses.map((c, i) => (
                      <tr key={i} className="border-b border-gray-800">
                        <td className="py-2 text-white max-w-xs truncate" title={c.title}>
                          {c.title}
                        </td>
                        <td className="py-2 text-right font-mono text-gray-300">{c.payments}</td>
                        <td className="py-2 text-right font-mono text-white">
                          {c.turnover.toLocaleString('ru-RU')} ₽
                        </td>
                        <td className="py-2 text-right font-mono text-neon-green">
                          {c.income.toLocaleString('ru-RU')} ₽
                        </td>
                        <td className="py-2 text-right font-mono text-crimson-alert">
                          {c.refunds > 0 ? `-${c.refunds.toLocaleString('ru-RU')} ₽` : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'recent' && (
            <div className="glass-panel p-6">
              <h3 className="text-white font-medium mb-4">Последние операции</h3>
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
                    {recent_payments.map((p, i) => (
                      <tr key={i} className="border-b border-gray-800">
                        <td className="py-2 text-gray-300">
                          {new Date(p.time).toLocaleDateString('ru-RU')}
                        </td>
                        <td className="py-2 text-white max-w-xs truncate" title={p.course}>
                          {p.course}
                        </td>
                        <td className="py-2 text-right font-mono text-white">
                          {p.payment_amount.toLocaleString('ru-RU')} ₽
                        </td>
                        <td className={`py-2 text-right font-mono ${p.status === 'refunded' ? 'text-crimson-alert' : 'text-neon-green'}`}>
                          {p.status === 'refunded' ? '−' : ''}{p.amount.toLocaleString('ru-RU')} ₽
                        </td>
                        <td className={`py-2 text-center text-sm font-medium ${STATUS_COLORS[p.status] || 'text-gray-400'}`}>
                          {STATUS_LABELS[p.status] || p.status}
                        </td>
                        <td className="py-2 text-center text-gray-500 text-sm">
                          {p.promo_code || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
