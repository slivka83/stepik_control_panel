import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api';
import { useRowsPerPage, useSortState } from '../components/DataTable';
import { useAuth } from '../contexts/AuthContext';
import { useSync } from '../contexts/SyncContext';

/**
 * Server-side table state: paging, sorting and fetching from an endpoint that
 * accepts `skip/limit/sort/order` (and optional extra params) and answers with
 * `{ [resultKey]: rows, total }`.
 *
 * Used by Студенты and by the comment lists (unanswered/disliked).
 *
 * - `enabled`     — fetch only when true (lazy tabs);
 * - `resetKey`    — changing it resets to page 1 (filter/tab changes);
 * - `extraParams` — extra query params (e.g. `type` for comment lists);
 * - `resetPageOnSync` — after a new sync, go to page 1 (comment lists) or
 *   just refetch the current page (students).
 */
export function useServerTable({
  endpoint,
  columns,
  initialSort,
  resultKey,
  enabled = true,
  resetKey = '',
  extraParams,
  resetPageOnSync = false,
}) {
  const { selectedCourseIds, syncStatus } = useSync();
  const { loading: authLoading } = useAuth();
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);
  // Start as loading so the empty-state row is not rendered for one tick and
  // then replaced by the first response (detached-node flakiness in tests).
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const { tableRef, rowsPerPage } = useRowsPerPage(rows.length);
  const { sort, onSort } = useSortState(columns, initialSort);

  const reqIdRef = useRef(0);
  const firstRenderRef = useRef(true);
  const prevLastSyncRef = useRef(undefined);
  const extraKey = JSON.stringify(extraParams ?? {});
  // A direct link (?tab=unanswered) or /students can mount before /auth/me
  // resolves. Fetching then returns 401 and leaves a permanent error banner;
  // wait for the session check to finish (it retries network errors itself).
  const active = enabled && !authLoading;

  const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
  const safePage = Math.min(page, totalPages);

  const fetchPage = useCallback(async () => {
    const id = ++reqIdRef.current;
    setLoading(true);
    setError(null);
    const filterParams = {};
    if (selectedCourseIds !== null) filterParams.course_ids = selectedCourseIds.join(',');
    try {
      const res = await api.get(endpoint, {
        params: {
          skip: (safePage - 1) * rowsPerPage,
          limit: rowsPerPage,
          sort: sort.key,
          order: sort.dir,
          ...JSON.parse(extraKey),
          ...filterParams,
        },
      });
      if (reqIdRef.current !== id) return;
      setRows(res.data[resultKey] || []);
      setTotal(res.data.total || 0);
      setError(null);
    } catch (e) {
      if (reqIdRef.current !== id) return;
      setError(e.response?.data?.detail || e.message || 'Не удалось загрузить данные');
    } finally {
      if (reqIdRef.current === id) setLoading(false);
    }
  }, [endpoint, resultKey, safePage, rowsPerPage, sort.key, sort.dir, selectedCourseIds, extraKey]);

  useEffect(() => {
    if (!enabled) {
      reqIdRef.current += 1;
      setLoading(false);
      return;
    }
    // Keep the table in loading state while /auth/me is unresolved (instead
    // of flashing the empty-state row and removing it a tick later).
    if (authLoading) return;
    fetchPage();
  }, [enabled, authLoading, fetchPage]);

  useEffect(() => {
    // Previous tab/filter rows must not be shown under the new heading while
    // the request is in flight (or if it fails).
    setRows([]);
    setTotal(0);
    setError(null);
  }, [resetKey, extraKey, selectedCourseIds]);

  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    setPage(1);
  }, [sort.key, sort.dir, resetKey]);

  useEffect(() => {
    const changed =
      prevLastSyncRef.current !== undefined && syncStatus.last_sync !== prevLastSyncRef.current;
    prevLastSyncRef.current = syncStatus.last_sync;
    if (!active || !changed) return;
    // setPage(1) на уже первой странице — no-op, поэтому явно перезапрашиваем:
    // иначе список остаётся со старыми строками после синка.
    if (resetPageOnSync && page !== 1) setPage(1);
    else fetchPage();
  }, [syncStatus.last_sync, active, resetPageOnSync, fetchPage, page]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  return {
    rows,
    total,
    error,
    loading,
    page,
    setPage,
    sort,
    onSort,
    rowsPerPage,
    tableRef,
    totalPages,
    refetch: fetchPage,
  };
}
