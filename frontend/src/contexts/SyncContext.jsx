import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from './AuthContext';
import api from '../api';

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
    courses: [],
    financials: null,
    submissions: null,
    comments: null,
    activeStudents: { months: [] },
    certificates: { months: [] },
    certificatesStats: null,
    reviewsStats: null,
  });
  const abortRef = useRef(null);
  const pollIntervalRef = useRef(30000);
  const filterRef = useRef(null);
  const fetchIdRef = useRef(0);

  const SYNC_POLL_INTERVAL_MS = 2000;

  const fetchAll = useCallback(async (signal) => {
    const myId = ++fetchIdRef.current;
    try {
      const courseIds = filterRef.current;
      const courseParams = courseIds === null ? {} : { params: { course_ids: courseIds.join(',') } };
      const [
        kpiRes,
        cohortsRes,
        revenueRes,
        coursesRes,
        financialsRes,
        submissionsRes,
        commentsRes,
        activeStudentsRes,
        certificatesRes,
        certificatesStatsRes,
        reviewsStatsRes,
      ] = await Promise.allSettled([
        api.get('/dashboard/kpi', { signal, ...courseParams }),
        api.get('/dashboard/cohorts', { signal, ...courseParams }),
        api.get('/dashboard/revenue', { signal, ...courseParams }),
        api.get('/courses', { signal }),
        api.get('/financials', { signal, ...courseParams }),
        api.get('/dashboard/submissions', { signal, ...courseParams }),
        api.get('/dashboard/comments', { signal, ...courseParams }),
        api.get('/dashboard/active-students', { signal, ...courseParams }),
        api.get('/dashboard/certificates', { signal, ...courseParams }),
        api.get('/dashboard/certificates/stats', { signal, ...courseParams }),
        api.get('/dashboard/reviews/stats', { signal, ...courseParams }),
      ]);

      if (myId !== fetchIdRef.current) return;

      setData((prev) => {
        const next = {
          ...prev,
          kpi: kpiRes.status === 'fulfilled' ? kpiRes.value.data : prev.kpi,
          cohorts: cohortsRes.status === 'fulfilled' ? cohortsRes.value.data : prev.cohorts,
          revenue: revenueRes.status === 'fulfilled' ? revenueRes.value.data : prev.revenue,
          courses: coursesRes.status === 'fulfilled' ? coursesRes.value.data.courses || [] : prev.courses,
          financials: financialsRes.status === 'fulfilled' ? financialsRes.value.data : prev.financials,
          submissions: submissionsRes.status === 'fulfilled' ? submissionsRes.value.data : prev.submissions,
          comments: commentsRes.status === 'fulfilled' ? commentsRes.value.data : prev.comments,
          activeStudents: activeStudentsRes.status === 'fulfilled' ? activeStudentsRes.value.data : prev.activeStudents,
          certificates: certificatesRes.status === 'fulfilled' ? certificatesRes.value.data : prev.certificates,
          certificatesStats:
            certificatesStatsRes.status === 'fulfilled' ? certificatesStatsRes.value.data : prev.certificatesStats,
          reviewsStats: reviewsStatsRes.status === 'fulfilled' ? reviewsStatsRes.value.data : prev.reviewsStats,
        };
        return next;
      });

      const failures = [
        kpiRes,
        cohortsRes,
        revenueRes,
        coursesRes,
        financialsRes,
        submissionsRes,
        commentsRes,
        activeStudentsRes,
        certificatesRes,
        certificatesStatsRes,
        reviewsStatsRes,
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
    const next = {
      in_progress: status?.in_progress ?? false,
      last_sync: status?.last_sync ?? null,
      last_error: status?.last_error ?? null,
      progress: status?.progress ?? 0,
      step: status?.step ?? null,
      cooldown_remaining_seconds: status?.cooldown_remaining_seconds ?? 0,
    };
    setSyncStatus((prev) => {
      if (
        prev.in_progress === next.in_progress &&
        prev.last_sync === next.last_sync &&
        prev.last_error === next.last_error &&
        prev.progress === next.progress &&
        prev.step === next.step &&
        prev.cooldown_remaining_seconds === next.cooldown_remaining_seconds
      )
        return prev;
      return next;
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
      if (!authLoading && !user) {
        setData({
          kpi: null, cohorts: {}, revenue: { months: [] },
          courses: [], financials: null, submissions: null, comments: null,
          activeStudents: { months: [] },
          certificates: { months: [] }, certificatesStats: null, reviewsStats: null,
        });
      }
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
      refresh: () => fetchAll(abortRef.current?.signal),
      updateSyncStatus,
      selectedCourseIds,
      isFilterActive: selectedCourseIds !== null,
      toggleCourse,
      selectAllCourses,
      selectNoneCourses,
    }),
    [
      syncStatus,
      data,
      loading,
      error,
      fetchAll,
      updateSyncStatus,
      selectedCourseIds,
      toggleCourse,
      selectAllCourses,
      selectNoneCourses,
    ],
  );

  return <SyncContext.Provider value={contextValue}>{children}</SyncContext.Provider>;
}

export const useSync = () => useContext(SyncContext);
