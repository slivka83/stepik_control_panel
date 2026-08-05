import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from './AuthContext';
import api from '../api';
import { mergePublishedIntoSubmissions } from '../utils/mergePublished';

const SyncContext = createContext();

export { SyncContext };

export function SyncProvider({ children }) {
  const { user, loading: authLoading } = useAuth();
  const [syncStatus, setSyncStatus] = useState({ in_progress: false, last_sync: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
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
    certificates: { months: [] },
    students: { students: [], total: 0 },
  });
  const abortRef = useRef(null);
  const pollIntervalRef = useRef(30000);
  const filterRef = useRef(null);

  const SYNC_POLL_INTERVAL_MS = 2000;

  const fetchAll = useCallback(async (signal) => {
    try {
      const courseIds = filterRef.current;
      const courseParams =
        courseIds === null ? {} : { params: { course_ids: courseIds.join(',') } };
      const [
        kpiRes,
        cohortsRes,
        revenueRes,
        alertsRes,
        coursesRes,
        financialsRes,
        submissionsRes,
        activeStudentsRes,
        activeEnrolledRes,
        publishedSolutionsRes,
        certificatesRes,
        studentsRes,
      ] = await Promise.allSettled([
        api.get('/dashboard/kpi', { signal, ...courseParams }),
        api.get('/dashboard/cohorts', { signal, ...courseParams }),
        api.get('/dashboard/revenue', { signal, ...courseParams }),
        api.get('/dashboard/alerts', { signal, ...courseParams }),
        api.get('/courses', { signal }),
        api.get('/financials', { signal, ...courseParams }),
        api.get('/dashboard/submissions', { signal, ...courseParams }),
        api.get('/dashboard/active-students', { signal, ...courseParams }),
        api.get('/dashboard/active-enrolled-students', { signal, ...courseParams }),
        api.get('/dashboard/published-solutions', { signal, ...courseParams }),
        api.get('/dashboard/certificates', { signal, ...courseParams }),
        api.get('/dashboard/students?limit=200', { signal, ...courseParams }),
      ]);

      setData((prev) => {
        const next = {
          ...prev,
          kpi: kpiRes.status === 'fulfilled' ? kpiRes.value.data : prev.kpi,
          cohorts: cohortsRes.status === 'fulfilled' ? cohortsRes.value.data : prev.cohorts,
          revenue: revenueRes.status === 'fulfilled' ? revenueRes.value.data : prev.revenue,
          alerts: alertsRes.status === 'fulfilled' ? alertsRes.value.data.alerts || [] : prev.alerts,
          courses: coursesRes.status === 'fulfilled' ? coursesRes.value.data.courses || [] : prev.courses,
          financials: financialsRes.status === 'fulfilled' ? financialsRes.value.data : prev.financials,
          submissions:
            submissionsRes.status === 'fulfilled'
              ? mergePublishedIntoSubmissions(
                  submissionsRes.value.data,
                  publishedSolutionsRes.status === 'fulfilled'
                    ? publishedSolutionsRes.value.data
                    : prev.publishedSolutions,
                )
              : prev.submissions,
          activeStudents: activeStudentsRes.status === 'fulfilled' ? activeStudentsRes.value.data : prev.activeStudents,
          activeEnrolled: activeEnrolledRes.status === 'fulfilled' ? activeEnrolledRes.value.data : prev.activeEnrolled,
          publishedSolutions:
            publishedSolutionsRes.status === 'fulfilled' ? publishedSolutionsRes.value.data : prev.publishedSolutions,
          certificates:
            certificatesRes.status === 'fulfilled' ? certificatesRes.value.data : prev.certificates,
          students: studentsRes.status === 'fulfilled' ? studentsRes.value.data : prev.students,
        };
        if (JSON.stringify(prev) === JSON.stringify(next)) return prev;
        return next;
      });

      const failures = [
        kpiRes,
        cohortsRes,
        revenueRes,
        alertsRes,
        coursesRes,
        financialsRes,
        submissionsRes,
        activeStudentsRes,
        activeEnrolledRes,
        publishedSolutionsRes,
        certificatesRes,
        studentsRes,
      ].filter((r) => r.status === 'rejected');
      if (failures.length > 0) {
        setError(`${failures.length} endpoint(s) failed to load`);
      } else {
        setError(null);
      }
      pollIntervalRef.current = 30000;
    } catch (err) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
        setError(err.message);
        pollIntervalRef.current = Math.min(pollIntervalRef.current * 2, 300000);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSyncStatus = useCallback((status) => {
    setSyncStatus((prev) => {
      if (
        prev.in_progress === status.in_progress &&
        prev.last_sync === status.last_sync &&
        prev.last_error === status.last_error &&
        prev.progress === status.progress &&
        prev.step === status.step
      )
        return prev;
      return status;
    });
  }, []);

  const [selectedCourseIds, setSelectedCourseIds] = useState(null);

  const applyFilter = useCallback(
    (ids) => {
      filterRef.current = ids;
      setSelectedCourseIds(ids);
      fetchAll(abortRef.current?.signal);
    },
    [fetchAll],
  );

  const toggleCourse = useCallback(
    (id) => {
      const available = (data.courses || []).map((c) => c.id);
      const prev = filterRef.current;
      let next;
      if (prev === null) {
        next = available.filter((cid) => cid !== id);
      } else if (prev.includes(id)) {
        next = prev.filter((cid) => cid !== id);
      } else {
        next = [...prev, id];
      }
      if (next.length >= available.length) next = null;
      applyFilter(next);
    },
    [data.courses, applyFilter],
  );

  const selectAllCourses = useCallback(() => {
    applyFilter(null);
  }, [applyFilter]);

  const selectNoneCourses = useCallback(() => {
    applyFilter([]);
  }, [applyFilter]);

  useEffect(() => {
    const ids = filterRef.current;
    if (!ids || ids.length === 0) return;
    const available = new Set((data.courses || []).map((c) => c.id));
    const pruned = ids.filter((id) => available.has(id));
    if (pruned.length !== ids.length) applyFilter(pruned.length ? pruned : []);
  }, [data.courses, applyFilter]);

  useEffect(() => {
    if (authLoading || !user) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    fetchAll(controller.signal);

    let lastKnownSync = null;
    let timer = null;
    const poll = async () => {
      try {
        const { data: status } = await api.get('/sync/status', { signal: controller.signal });
        updateSyncStatus(status);
        if (lastKnownSync && status.last_sync && lastKnownSync !== status.last_sync) {
          fetchAll(controller.signal);
        }
        lastKnownSync = status.last_sync;
        timer = setTimeout(poll, status.in_progress ? SYNC_POLL_INTERVAL_MS : pollIntervalRef.current);
      } catch {
        timer = setTimeout(poll, pollIntervalRef.current);
      }
    };

    timer = setTimeout(poll, 0);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [user, authLoading, fetchAll]);

  const contextValue = useMemo(
    () => ({
      syncStatus,
      data,
      loading,
      error,
      refresh: () => fetchAll(),
      updateSyncStatus,
      selectedCourseIds,
      isFilterActive: selectedCourseIds !== null,
      toggleCourse,
      selectAllCourses,
      selectNoneCourses,
    }),
    [syncStatus, data, loading, error, fetchAll, updateSyncStatus, selectedCourseIds, toggleCourse, selectAllCourses, selectNoneCourses],
  );

  return <SyncContext.Provider value={contextValue}>{children}</SyncContext.Provider>;
}

export const useSync = () => useContext(SyncContext);
