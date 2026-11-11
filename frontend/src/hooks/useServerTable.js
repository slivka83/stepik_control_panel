import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api';
import { useRowsPerPage, useSortState } from '../components/DataTable';
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
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const { tableRef, rowsPerPage } = useRowsPerPage();
  const { sort, onSort } = useSortState(columns, initialSort);

  const reqIdRef = useRef(0);
  const firstRenderRef = useRef(true);
  const prevLastSyncRef = useRef(null);
  const extraKey = JSON.stringify(extraParams ?? {});

  const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
  const safePage = Math.min(page, totalPages);

  const fetchPage = useCallback(async () => {
    const id = ++reqIdRef.current;
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
      setError(e.message);
    }
  }, [endpoint, resultKey, safePage, rowsPerPage, sort.key, sort.dir, selectedCourseIds, extraKey]);

  useEffect(() => {
    if (enabled) fetchPage();
  }, [enabled, fetchPage]);

  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    setPage(1);
  }, [sort.key, sort.dir, resetKey]);

  useEffect(() => {
    if (
      enabled &&
      prevLastSyncRef.current !== null &&
      syncStatus.last_sync !== prevLastSyncRef.current
    ) {
      if (resetPageOnSync) setPage(1);
      else fetchPage();
    }
    prevLastSyncRef.current = syncStatus.last_sync;
  }, [syncStatus.last_sync, enabled, resetPageOnSync, fetchPage]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  return {
    rows,
    total,
    error,
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
