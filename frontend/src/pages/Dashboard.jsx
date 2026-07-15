import { useState, useEffect } from 'react'
import axios from 'axios'
import KpiCard from '../components/KpiCard'
import RevenueChart from '../components/RevenueChart'
import CohortChart from '../components/CohortChart'

export default function Dashboard() {
  const [kpi, setKpi] = useState(null)
  const [cohorts, setCohorts] = useState({})
  const [revenue, setRevenue] = useState({ months: [] })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [kpiRes, cohortsRes, revenueRes] = await Promise.all([
          axios.get('/api/dashboard/kpi'),
          axios.get('/api/dashboard/cohorts'),
          axios.get('/api/dashboard/revenue'),
        ])
        setKpi(kpiRes.data)
        setCohorts(cohortsRes.data)
        setRevenue(revenueRes.data)
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
        <div className="text-xs text-gray-500 font-mono">
          Last sync: {new Date().toLocaleString('ru-RU')}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Доход за месяц"
          value={kpi?.total_revenue || 0}
          suffix=" ₽"
          color="neon-green"
          trend={12}
        />
        <KpiCard
          title="Студенты"
          value={kpi?.total_students || 0}
          color="cyber-blue"
          trend={8}
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

      <div className="glass-panel p-6">
        <h3 className="text-white font-medium mb-4">Алерты</h3>
        <div className="space-y-3">
          <div className="flex items-center gap-3 p-3 bg-amber-alert/10 border border-amber-alert/20 rounded-lg">
            <span className="text-amber-alert">⚠</span>
            <span className="text-sm text-gray-300">
              14 студентов набрали проходной балл, но не получили сертификат
            </span>
            <a
              href="https://stepik.org/course/1/certificates"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-xs text-cyber-blue hover:underline font-mono"
            >
              Открыть на Stepik →
            </a>
          </div>
          <div className="flex items-center gap-3 p-3 bg-crimson-alert/10 border border-crimson-alert/20 rounded-lg">
            <span className="text-crimson-alert">✕</span>
            <span className="text-sm text-gray-300">
              3 битых ссылки обнаружено в модуле "Основы Python"
            </span>
            <a
              href="https://stepik.org/course/1/lessons"
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-xs text-cyber-blue hover:underline font-mono"
            >
              Исправить на Stepik →
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
