import { useState, useEffect, useRef, useCallback } from 'react';
import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import StudentsBar from '../components/StudentsBar';
import DataTable, { useRowsPerPage, useSortState } from '../components/DataTable';
import { fmtDate } from '../utils/format';
import api from '../api';

const COHORT_COLORS = {
  Active: '#4ade80',
  Passive: '#38bdf8',
  Fading: '#f59e0b',
  Sleeping: '#f43f5e',
  Zombie: '#a855f7',
};

const STUDENT_COLUMNS = [
  {
    key: 'name',
    label: 'Имя',
    width: 'w-[22%]',
    render: (s) => (
      <td className="pl-1 pr-1 truncate">
        <a
          href={s.profile_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyber-blue font-mono text-xs hover:underline truncate block"
          title={s.name || `Студент ${s.student_id}`}
        >
          {s.name || `Студент ${s.student_id}`}
        </a>
      </td>
    ),
  },
  {
    key: 'cohort_status',
    label: 'Статус',
    width: 'w-[9%]',
    render: (s) => (
      <td className="pl-1 pr-1">
        <span
          className="inline-block px-2 rounded text-xs font-medium"
          style={{
            backgroundColor: `${COHORT_COLORS[s.cohort_status] || '#6b7280'}20`,
            color: COHORT_COLORS[s.cohort_status] || '#6b7280',
          }}
        >
          {s.cohort_status}
        </span>
      </td>
    ),
  },
  { key: 'courses_count', label: 'Курсы', align: 'right', width: 'w-[8%]', numeric: true },
  { key: 'certificates', label: 'Сертификаты', align: 'right', width: 'w-[11%]', numeric: true },
  {
    key: 'submissions_count',
    label: 'Решения',
    align: 'right',
    width: 'w-[13%]',
    numeric: true,
    render: (s) => (
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">
        {s.submissions_count > 0
          ? `${s.submissions_count} (${Math.round(((s.submissions_successful || 0) / s.submissions_count) * 100)}%)`
          : '0'}
      </td>
    ),
  },
  { key: 'published_solutions', label: 'Опубликованные', align: 'right', width: 'w-[12%]', numeric: true },
  { key: 'comments_count', label: 'Комментарии', align: 'right', width: 'w-[11%]', numeric: true },
  {
    key: 'last_activity',
    label: 'Активность',
    align: 'right',
    width: 'w-[14%]',
    nullLast: true,
    naturalDir: 'asc',
    render: (s) => (
      <td className="text-right font-mono text-xs text-gray-400 pl-1 pr-1 whitespace-nowrap">
        {fmtDate(s.last_activity)}
      </td>
    ),
  },
];

export default function Students() {
  const { data, error: syncError, refresh, selectedCourseIds, syncStatus } = useSync();
  const cohorts = data.cohorts;
  const [students, setStudents] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const { tableRef, rowsPerPage } = useRowsPerPage();
  const { sort, onSort } = useSortState(STUDENT_COLUMNS, { key: 'last_activity', dir: 'desc' });
  const reqIdRef = useRef(0);
  const firstRenderRef = useRef(true);
  const prevLastSyncRef = useRef(null);

  const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
  const safePage = Math.min(page, totalPages);

  const fetchPage = useCallback(async () => {
    const id = ++reqIdRef.current;
    const params = {};
    if (selectedCourseIds !== null) params.course_ids = selectedCourseIds.join(',');
    try {
      const res = await api.get('/dashboard/students', {
        params: {
          skip: (safePage - 1) * rowsPerPage,
          limit: rowsPerPage,
          sort: sort.key,
          order: sort.dir,
          ...params,
        },
      });
      if (reqIdRef.current !== id) return;
      setStudents(res.data.students);
      setTotal(res.data.total);
      setError(null);
    } catch (e) {
      if (reqIdRef.current !== id) return;
      setError(e.message);
    }
  }, [safePage, rowsPerPage, sort.key, sort.dir, selectedCourseIds]);

  useEffect(() => {
    fetchPage();
  }, [fetchPage]);

  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    setPage(1);
  }, [selectedCourseIds]);

  useEffect(() => {
    if (prevLastSyncRef.current !== null && syncStatus.last_sync !== prevLastSyncRef.current) {
      fetchPage();
    }
    prevLastSyncRef.current = syncStatus.last_sync;
  }, [syncStatus.last_sync, fetchPage]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const bannerError = error || syncError;
  const retry = () => {
    if (syncError) refresh();
    fetchPage();
  };

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {bannerError && <ErrorBanner message={bannerError} onRetry={retry} />}

      <StudentsBar data={cohorts} />

      <DataTable
        columns={STUDENT_COLUMNS}
        rows={students}
        initialSort={{ key: 'last_activity', dir: 'desc' }}
        sort={sort}
        onSort={onSort}
        page={page}
        setPage={setPage}
        rowsPerPage={rowsPerPage}
        tableRef={tableRef}
        totalPages={totalPages}
        rowKey={(s) => s.student_id}
        emptyText="Нет данных о студентах"
        panelClassName="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden"
      />
    </div>
  );
}
