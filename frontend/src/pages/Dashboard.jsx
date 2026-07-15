import { useState, useEffect } from 'react'
import api from '../api'
import KpiCard from '../components/KpiCard'
import RevenueChart from '../components/RevenueChart'
import CohortChart from '../components/CohortChart'

export default function Dashboard() {
  const [kpi, setKpi] = useState(null)
  const [cohorts, setCohorts] = useState({})
  const [revenue, setRevenue] = useState({ months: [] })
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [kpiRes, cohortsRes, revenueRes, alertsRes] = await Promise.all([
          api.get('/api/dashboard/kpi'),
          api.get('/api/dashboard/cohorts'),
          api.get('/api/dashboard/revenue'),
          api.get('/api/dashboard/alerts'),
        ])
        setKpi(kpiRes.data)
        setCohorts(cohortsRes.data)
        setRevenue(revenueRes.data)
        setAlerts(alertsRes.data.alerts || [])
      } catch (err) {
        console.error('Dashboard fetch error:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
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

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Доход за месяц"
          value={kpi?.total_revenue || 0}
          suffix=" ₽"
          color="neon-green"
        />
        <KpiCard
          title="Студенты"
          value={kpi?.total_students || 0}
          color="cyber-blue"
        />
        <KpiCard
          title="Сертификаты"
          value={kpi?.certificates_issued || 0}
          color="amber-alert"
        />
        <KpiCard
          title="Курсы"
          value={kpi?.courses_count || 0}
          color="cyber-blue"
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
