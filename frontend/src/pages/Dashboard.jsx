import { useState, useEffect, useRef } from 'react'
import api from '../api'
import { useSync } from '../contexts/SyncContext'
import { getCached, setCached } from '../cache'
import KpiCard from '../components/KpiCard'
import RevenueChart from '../components/RevenueChart'
import CohortChart from '../components/CohortChart'

export default function Dashboard() {
  const [kpi, setKpi] = useState(getCached('dash_kpi'))
  const [cohorts, setCohorts] = useState(getCached('dash_cohorts') || {})
  const [revenue, setRevenue] = useState(getCached('dash_revenue') || { months: [] })
  const [alerts, setAlerts] = useState(getCached('dash_alerts') || [])
  const loaded = useRef(!!getCached('dash_kpi'))
  const { refreshKey } = useSync()

  useEffect(() => {
    const fetchData = async () => {
      const [kpiRes, cohortsRes, revenueRes, alertsRes] = await Promise.allSettled([
        api.get('/api/dashboard/kpi'),
        api.get('/api/dashboard/cohorts'),
        api.get('/api/dashboard/revenue'),
        api.get('/api/dashboard/alerts'),
      ])
      if (kpiRes.status === 'fulfilled') {
        setKpi(kpiRes.value.data)
        setCached('dash_kpi', kpiRes.value.data)
      }
      if (cohortsRes.status === 'fulfilled') {
        setCohorts(cohortsRes.value.data)
        setCached('dash_cohorts', cohortsRes.value.data)
      }
      if (revenueRes.status === 'fulfilled') {
        setRevenue(revenueRes.value.data)
        setCached('dash_revenue', revenueRes.value.data)
      }
      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.data.alerts || [])
        setCached('dash_alerts', alertsRes.value.data.alerts || [])
      }
      loaded.current = true
    }
    fetchData()
  }, [refreshKey])

  if (!loaded.current) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-cyber-blue font-mono animate-pulse">Загрузка данных...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Сводная аналитика</h1>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard
          title="Доход за месяц"
          value={kpi?.total_revenue || 0}
          suffix=" ₽"
          color="neon-green"
        />
        <KpiCard
          title="Чистый доход"
          value={kpi?.net_income || 0}
          suffix=" ₽"
          color="cyber-blue"
        />
        <KpiCard
          title="Оборот"
          value={kpi?.total_turnover || 0}
          suffix=" ₽"
          color="amber-alert"
        />
        <KpiCard
          title="Студенты"
          value={kpi?.total_students || 0}
          color="cyber-blue"
        />
        <KpiCard
          title="Покупок"
          value={kpi?.total_payments || 0}
          color="neon-green"
        />
        <KpiCard
          title="Сертификаты"
          value={kpi?.certificates_issued || 0}
          color="amber-alert"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RevenueChart data={revenue.months} />
        <CohortChart data={cohorts} />
      </div>

      {alerts.length > 0 && (
        <div className="glass-panel p-6">
          <h3 className="text-white font-medium mb-4">Алерты</h3>
          <div className="space-y-3">
            {alerts.map((alert, i) => (
              <div
                key={i}
                className={`flex items-center gap-3 p-3 rounded-lg border ${
                  alert.type === 'warning'
                    ? 'bg-amber-alert/10 border-amber-alert/20'
                    : 'bg-crimson-alert/10 border-crimson-alert/20'
                }`}
              >
                <span className={alert.type === 'warning' ? 'text-amber-alert' : 'text-crimson-alert'}>
                  {alert.type === 'warning' ? '⚠' : '✕'}
                </span>
                <span className="text-sm text-gray-300">{alert.message}</span>
                {alert.link && (
                  <a
                    href={alert.link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="ml-auto text-xs text-cyber-blue hover:underline font-mono"
                  >
                    {alert.link_text || 'Открыть на Stepik →'}
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
