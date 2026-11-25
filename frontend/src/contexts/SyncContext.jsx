import { createContext, useContext, useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useAuth } from './AuthContext';
import api from '../api';

const SyncContext = createContext();

export { SyncContext };

const SYNC_POLL_INTERVAL_MS = 2000;
const IDLE_POLL_INTERVAL_MS = 30000;
const MAX_POLL_INTERVAL_MS = 300000;
// Retry a failed initial load (backend/database still booting after a restart)
// instead of leaving the panel empty until a manual sync.
const LOAD_RETRY_INITIAL_MS = 3000;
const LOAD_RETRY_MAX_MS = 30000;

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
  const retryTimerRef = useRef(null);
  const retryDelayRef = useRef(LOAD_RETRY_INITIAL_MS);
  const fetchAllRef = useRef(null);
  // Last last_sync the context has already reacted to. Manual status updates
  // (the sync button) move it forward too, so the next idle poll does not
  // trigger a second full dashboard reload.
  const lastKnownSyncRef = useRef(null);

  const fetchAll = useCallback(async (signal) => {
    clearTimeout(retryTimerRef.current);
    retryTimerRef.current = null;
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
      // Aborted request (filter switch, unmount, logout) must not overwrite the
      // newer data or raise a stale error banner.
      if (signal?.aborted) return;

      setData((prev) => {
        const next = { ...prev };
        const empty = courseIds === null ? null : emptyData();
        ENDPOINTS.forEach((ep, i) => {
          const result = results[i];
          if (result.status === 'fulfilled') {
            next[ep.key] = ep.select ? ep.select(result.value.data) : result.value.data;
          } else if (empty && !ep.unfiltered) {
            // При активном фильтре нельзя оставлять данные «всех курсов»
            // рядом с уже отфильтрованными: лучше пустая панель + баннер.
            // Список курсов (источник фильтра) не трогаем: иначе временный
            // сбой /courses сбросил бы выбранный фильтр.
            next[ep.key] = empty[ep.key];
          }
        });
        return next;
      });

      const failures = results.filter((r) => r.status === 'rejected').length;
      setError(failures > 0 ? `Не удалось загрузить данные (${failures})` : null);
      pollIntervalRef.current = IDLE_POLL_INTERVAL_MS;

      if (failures > 0 && !signal?.aborted) {
        retryTimerRef.current = setTimeout(() => {
          fetchAllRef.current?.(signal);
        }, retryDelayRef.current);
        retryDelayRef.current = Math.min(retryDelayRef.current * 2, LOAD_RETRY_MAX_MS);
      } else {
        retryDelayRef.current = LOAD_RETRY_INITIAL_MS;
      }
    } catch (err) {
      if (err.name !== 'CanceledError' && err.name !== 'AbortError') {
        setError(err.message);
        pollIntervalRef.current = Math.min(pollIntervalRef.current * 2, MAX_POLL_INTERVAL_MS);
        if (!signal?.aborted) {
          retryTimerRef.current = setTimeout(() => {
            fetchAllRef.current?.(signal);
          }, retryDelayRef.current);
          retryDelayRef.current = Math.min(retryDelayRef.current * 2, LOAD_RETRY_MAX_MS);
        }
      }
    } finally {
      if (myId === fetchIdRef.current && !signal?.aborted) setLoading(false);
    }
  }, []);

  fetchAllRef.current = fetchAll;

  const updateSyncStatus = useCallback((status) => {
    const next = normalizeSyncStatus(status);
    lastKnownSyncRef.current = next.last_sync;
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
      // Do not show numbers of the previous selection while the new filter
      // is loading. The course list stays: it is the filter's own source.
      setData((prev) => {
        const next = emptyData();
        next.courses = prev.courses;
        return next;
      });
      fetchAll(abortRef.current?.signal);
    },
    [fetchAll],
  );

  const toggleCourse = useCallback(
    (id) => {
      const available = (data.courses || []).map((c) => c.id);
      const availableSet = new Set(available);
      // Ignore ids of courses that disappeared since the filter was applied:
      // otherwise the "everything selected" shortcut fires while some visible
      // checkbox is still unchecked.
      const prev =
        filterRef.current === null
          ? null
          : filterRef.current.filter((cid) => availableSet.has(cid));
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
        filterRef.current = null;
        setSelectedCourseIds(null);
        setData(emptyData());
        setError(null);
      }
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    fetchAll(controller.signal);

    let firstPoll = true;
    let backendWasDown = false;
    let timer = null;
    const poll = async () => {
      try {
        const { data: status } = await api.get('/sync/status', { signal: controller.signal });
        const recovered = backendWasDown;
        const previousLastSync = lastKnownSyncRef.current;
        backendWasDown = false;
        updateSyncStatus(status);
        // Reload after a restart even when last_sync did not change: the tab
        // may have loaded its data before the backend was ready. The first
        // poll only records the baseline — otherwise an empty first-ever sync
        // (last_sync was null, then a timestamp) never triggered a reload.
        // Compare with the value from BEFORE updateSyncStatus: a manual sync
        // already updated the ref, so its next poll no longer reloads twice.
        if (recovered || (!firstPoll && status.last_sync !== previousLastSync)) {
          fetchAll(controller.signal);
        }
        firstPoll = false;
        timer = setTimeout(poll, status.in_progress ? SYNC_POLL_INTERVAL_MS : pollIntervalRef.current);
      } catch {
        if (controller.signal.aborted) return;
        backendWasDown = true;
        timer = setTimeout(poll, pollIntervalRef.current);
      }
    };

    timer = setTimeout(poll, 0);
    return () => {
      clearTimeout(timer);
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
      controller.abort();
    };
  }, [user, authLoading, fetchAll, updateSyncStatus]);

  // After the backend restarts (dev reload), an open tab keeps stale/empty data.
  // Reloading on focus makes the panel recover without a manual sync.
  useEffect(() => {
    if (!user) return undefined;
    let lastReloadAt = 0;
    const onFocus = () => {
      if (document.visibilityState === 'hidden') return;
      const now = Date.now();
      if (now - lastReloadAt < 1000) return;
      lastReloadAt = now;
      fetchAll(abortRef.current?.signal);
    };
    window.addEventListener('focus', onFocus);
    document.addEventListener('visibilitychange', onFocus);
    return () => {
      window.removeEventListener('focus', onFocus);
      document.removeEventListener('visibilitychange', onFocus);
    };
  }, [user, fetchAll]);

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
