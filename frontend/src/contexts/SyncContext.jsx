import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../api'

const SyncContext = createContext()

export function SyncProvider({ children }) {
  const [syncStatus, setSyncStatus] = useState({ in_progress: false, last_sync: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [data, setData] = useState({
    kpi: null,
    cohorts: {},
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials: null,
  })

  const fetchAll = useCallback(async () => {
    try {
      const [kpiRes, cohortsRes, revenueRes, alertsRes, coursesRes, financialsRes] =
        await Promise.allSettled([
          api.get('/api/dashboard/kpi'),
          api.get('/api/dashboard/cohorts'),
          api.get('/api/dashboard/revenue'),
          api.get('/api/dashboard/alerts'),
          api.get('/api/courses'),
          api.get('/api/financials'),
        ])

      setData(prev => ({
        ...prev,
        kpi: kpiRes.status === 'fulfilled' ? kpiRes.value.data : prev.kpi,
        cohorts: cohortsRes.status === 'fulfilled' ? cohortsRes.value.data : prev.cohorts,
        revenue: revenueRes.status === 'fulfilled' ? revenueRes.value.data : prev.revenue,
        alerts: alertsRes.status === 'fulfilled'
          ? (alertsRes.value.data.alerts || [])
          : prev.alerts,
        courses: coursesRes.status === 'fulfilled'
          ? (coursesRes.value.data.courses || [])
          : prev.courses,
        financials: financialsRes.status === 'fulfilled' ? financialsRes.value.data : prev.financials,
      }))

      const failures = [kpiRes, cohortsRes, revenueRes, alertsRes, coursesRes, financialsRes]
        .filter(r => r.status === 'rejected')
      if (failures.length > 0) {
        setError(`${failures.length} endpoint(s) failed to load`)
      } else {
        setError(null)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()

    let lastKnownSync = null
    const poll = async () => {
      try {
        const { data: status } = await api.get('/api/sync/status')
        setSyncStatus(status)
        if (lastKnownSync && status.last_sync && lastKnownSync !== status.last_sync) {
          fetchAll()
        }
        lastKnownSync = status.last_sync
      } catch {}
    }

    const interval = setInterval(poll, 30000)
    return () => clearInterval(interval)
  }, [fetchAll])

  return (
    <SyncContext.Provider value={{ syncStatus, data, loading, error, refresh: fetchAll }}>
      {children}
    </SyncContext.Provider>
  )
}

export const useSync = () => useContext(SyncContext)
