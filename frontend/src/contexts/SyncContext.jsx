import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from './AuthContext';
import api from '../api';

const SyncContext = createContext();

export { SyncContext };

const SYNC_POLL_INTERVAL_MS = 2000;
const IDLE_POLL_INTERVAL_MS = 30000;
const MAX_POLL_INTERVAL_MS = 300000;

// Every dashboard endpoint the panel loads. `select` reshapes the response
// (courses live under `.courses`), `unfiltered` keeps the course filter off
// (the courses list is the filter's own source).
const ENDPOINTS = [
  { key: 'kpi', url: '/dashboard/kpi' },
  { key: 'cohorts', url: '/dashboard/cohorts' },
  { key: 'revenue', url: '/dashboard/revenue' },
  { key: 'courses', url: '/courses', unfiltered: true, select: (data) => data.courses || [] },
  { key: 'financials', url: '/financials' },
  { key: 'submissions', url: '/dashboard/submissions' },
  { key: 'comments', url: '/dashboard/comments' },
  { key: 'activeStudents', url: '/dashboard/active-students' },
  { key: 'certificates', url: '/dashboard/certificates' },
  { key: 'certificatesStats', url: '/dashboard/certificates/stats' },
  { key: 'reviewsStats', url: '/dashboard/reviews/stats' },
];

function emptyData() {
  return {
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
  };
}

function normalizeSyncStatus(status) {
  return {
    in_progress: status?.in_progress ?? false,
    last_sync: status?.last_sync ?? null,
    last_error: status?.last_error ?? null,
    progress: status?.progress ?? 0,
    step: status?.step ?? null,
    cooldown_remaining_seconds: status?.cooldown_remaining_seconds ?? 0,
  };
}

export function SyncProvider({ children }) {
  const { user, loading: authLoading } = useAuth();
  const [syncStatus, setSyncStatus] = useState({ in_progress: false, last_sync: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(emptyData);
  const abortRef = useRef(null);
  const pollIntervalRef = useRef(IDLE_POLL_INTERVAL_MS);
  const filterRef = useRef(null);
  const fetchIdRef = useRef(0);

  const fetchAll = useCallback(async (signal) => {
    const myId = ++fetchIdRef.current;
    try {
      const courseIds = filterRef.current;
      const courseParams = courseIds === null ? {} : { params: { course_ids: courseIds.join(',') } };
      const results = await Promise.allSettled(
        ENDPOINTS.map((ep) =>
          api.get(ep.url, ep.unfiltered ? { signal } : { signal, ...courseParams }),
        ),
      );

      if (myId !== fetchIdRef.current) return;

      setData((prev) => {
        const next = { ...prev };
        ENDPOINTS.forEach((ep, i) => {
          const result = results[i];
          if (result.status === 'fulfilled') {
            next[ep.key] = ep.select ? ep.select(result.value.data) : result.value.data;
          }
        });
        return next;
      });

      const failures = results.filter((r) => r.status === 'rejected').length;
      setError(failures > 0 ? `${failures} endpoint(s) failed to load` : null);
      pollIntervalRef.current = IDLE_POLL_INTERVAL_MS;
    } catch (err) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
        setError(err.message);
        pollIntervalRef.current = Math.min(pollIntervalRef.current * 2, MAX_POLL_INTERVAL_MS);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const updateSyncStatus = useCallback((status) => {
    const next = normalizeSyncStatus(status);
    setSyncStatus((prev) => {
      const unchanged = Object.keys(next).every((key) => prev[key] === next[key]);
      return unchanged ? prev : next;
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
        setData(emptyData());
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
  }, [user, authLoading, fetchAll, updateSyncStatus]);

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
