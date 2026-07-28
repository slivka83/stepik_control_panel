import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useAuth } from './AuthContext'
import api from '../api'

const SyncContext = createContext()

export { SyncContext }

export function SyncProvider({ children }) {
  const { user, loading: authLoading } = useAuth()
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
    submissions: null,
    activeStudents: { months: [] },
    activeEnrolled: { months: [] },
    publishedSolutions: { months: [] },
  })
  const abortRef = useRef(null)
  const pollIntervalRef = useRef(30000)

  const fetchAll = useCallback(async (signal) => {
    try {
      const [kpiRes, cohortsRes, revenueRes, alertsRes, coursesRes, financialsRes, submissionsRes, activeStudentsRes, activeEnrolledRes, publishedSolutionsRes] =
        await Promise.allSettled([
          api.get('/dashboard/kpi', { signal }),
          api.get('/dashboard/cohorts', { signal }),
          api.get('/dashboard/revenue', { signal }),
          api.get('/dashboard/alerts', { signal }),
          api.get('/courses', { signal }),
          api.get('/financials', { signal }),
          api.get('/dashboard/submissions', { signal }),
          api.get('/dashboard/active-students', { signal }),
          api.get('/dashboard/active-enrolled-students', { signal }),
          api.get('/dashboard/published-solutions', { signal }),
        ])

      setData(prev => {
        const next = {
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
          submissions: submissionsRes.status === 'fulfilled' ? submissionsRes.value.data : prev.submissions,
          activeStudents: activeStudentsRes.status === 'fulfilled' ? activeStudentsRes.value.data : prev.activeStudents,
          activeEnrolled: activeEnrolledRes.status === 'fulfilled' ? activeEnrolledRes.value.data : prev.activeEnrolled,
          publishedSolutions: publishedSolutionsRes.status === 'fulfilled' ? publishedSolutionsRes.value.data : prev.publishedSolutions,
        }
        if (JSON.stringify(prev) === JSON.stringify(next)) return prev
        return next
      })

      const failures = [kpiRes, cohortsRes, revenueRes, alertsRes, coursesRes, financialsRes, submissionsRes, activeStudentsRes, activeEnrolledRes, publishedSolutionsRes]
        .filter(r => r.status === 'rejected')
      if (failures.length > 0) {
        setError(`${failures.length} endpoint(s) failed to load`)
      } else {
        setError(null)
      }
      pollIntervalRef.current = 30000
    } catch (err) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
        setError(err.message)
        pollIntervalRef.current = Math.min(pollIntervalRef.current * 2, 300000)
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (authLoading || !user) {
      setLoading(false)
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    fetchAll(controller.signal)

    let lastKnownSync = null
    const poll = async () => {
      try {
        const { data: status } = await api.get('/sync/status', { signal: controller.signal })
        setSyncStatus(prev => {
          if (prev.in_progress === status.in_progress && prev.last_sync === status.last_sync) return prev
          return status
        })
        if (lastKnownSync && status.last_sync && lastKnownSync !== status.last_sync) {
          fetchAll(controller.signal)
        }
        lastKnownSync = status.last_sync
      } catch {
        // aborted or network error
      }
    }

    const interval = setInterval(poll, pollIntervalRef.current)
    return () => {
      controller.abort()
      clearInterval(interval)
    }
  }, [user, authLoading, fetchAll])

  const contextValue = useMemo(
    () => ({ syncStatus, data, loading, error, refresh: () => fetchAll() }),
    [syncStatus, data, loading, error, fetchAll]
  )

  return (
    <SyncContext.Provider value={contextValue}>
      {children}
    </SyncContext.Provider>
  )
}

export const useSync = () => useContext(SyncContext)
