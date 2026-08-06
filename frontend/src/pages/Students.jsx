import { memo, useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react';
import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import StudentsBar from '../components/StudentsBar';
import api from '../api';

const COHORT_COLORS = {
  Active: '#4ade80',
  Passive: '#38bdf8',
  Fading: '#f59e0b',
  Sleeping: '#f43f5e',
  Zombie: '#a855f7',
};

const ROW_HEIGHT = 35;

function calcRowsPerPage(node) {
  const header = node.querySelector('thead');
  const headerH = header?.offsetHeight || 0;
  const row = node.querySelector('tbody tr');
  const rowH = row?.offsetHeight || ROW_HEIGHT;
  const avail = node.clientHeight - headerH - 4;
  return Math.max(1, Math.floor(avail / rowH));
}

const SORT_COLUMNS = {
  name: { numeric: false },
  cohort_status: { numeric: false },
  courses_count: { numeric: true },
  certificates: { numeric: true },
  submissions_count: { numeric: true },
  comments_count: { numeric: true },
  published_solutions: { numeric: true },
  last_activity: { numeric: false, nullLast: true },
};

const NATURAL_DIR_BY_KEY = {
  name: 'desc',
  cohort_status: 'desc',
  courses_count: 'asc',
  certificates: 'asc',
  submissions_count: 'asc',
  comments_count: 'asc',
  published_solutions: 'asc',
  last_activity: 'asc',
};

const makeSortHandler = (setter, config) => (key) => {
  setter((state) =>
    state.key === key
      ? { key, dir: state.dir === 'asc' ? 'desc' : 'asc' }
      : { key, dir: config[key].numeric ? 'desc' : 'asc' },
  );
};

const SortableTh = memo(function SortableTh({ label, sortKey, sort, onSort, align = 'left', width }) {
  const active = sort.key === sortKey;
  const arrow = (
    <span className={`shrink-0 ${active ? 'text-cyber-blue' : 'invisible'}`}>{sort.dir === NATURAL_DIR_BY_KEY[sortKey] ? '↓' : '↑'}</span>
  );
  return (
    <th
      className={`pb-2 pl-1 pr-1 font-normal text-gray-400 cursor-pointer select-none hover:text-gray-300 transition-colors ${align === 'right' ? 'text-right' : 'text-left'} ${width || ''}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {align === 'right' && arrow}
        <span>{label}</span>
        {align === 'left' && arrow}
      </span>
    </th>
  );
});

function Pagination({ page, totalPages, setPage }) {
  if (totalPages <= 1) return null;
  return (
    <div className="flex items-center justify-between mt-3 pl-1 pr-1 shrink-0">
      <span className="text-xs text-gray-500">
        Страница {page} из {totalPages}
      </span>
      <div className="flex gap-2">
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page === 1}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          ← Назад
        </button>
        <button
          onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          disabled={page === totalPages}
          className="px-3 py-1 text-xs text-cyber-blue border border-cyber-blue/30 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed hover:bg-cyber-blue/10 transition-colors"
        >
          Вперёд →
        </button>
      </div>
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}.${mm}.${yyyy}`;
}

const StudentRow = memo(function StudentRow({ student: s }) {
  return (
    <tr className="border-b border-gray-800">
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
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{s.courses_count}</td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{s.certificates}</td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">
        {s.submissions_count > 0
          ? `${s.submissions_count} (${Math.round(((s.submissions_successful || 0) / s.submissions_count) * 100)}%)`
          : '0'}
      </td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{s.published_solutions}</td>
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">{s.comments_count}</td>
      <td className="text-right font-mono text-xs text-gray-400 pl-1 pr-1 whitespace-nowrap">
        {fmtDate(s.last_activity)}
      </td>
    </tr>
  );
});

export default function Students() {
  const { data, error: syncError, refresh, selectedCourseIds, syncStatus } = useSync();
  const cohorts = data.cohorts;
  const [students, setStudents] = useState([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState(null);
  const [sort, setSort] = useState({ key: 'last_activity', dir: 'desc' });
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const tableRef = useRef(null);
  const prevRows = useRef(0);
  const resizeRef = useRef(null);
  const reqIdRef = useRef(0);
  const firstRenderRef = useRef(true);
  const prevLastSyncRef = useRef(null);

  useLayoutEffect(() => {
    const node = tableRef.current;
    if (!node) return;
    const calc = calcRowsPerPage(node);
    if (calc !== prevRows.current) {
      prevRows.current = calc;
      setRowsPerPage(calc);
    }
  });

  useEffect(() => {
    prevRows.current = 0;
    const node = tableRef.current;
    if (!node) return;
    const ro = new ResizeObserver(() => {
      const calc = calcRowsPerPage(node);
      if (calc !== prevRows.current) {
        prevRows.current = calc;
        setRowsPerPage(calc);
      }
    });
    resizeRef.current = ro;
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const onSort = makeSortHandler(setSort, SORT_COLUMNS);

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

      <div className="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
          <table className="w-full text-sm table-fixed fin-table sol-table">
            <thead>
              <tr className="border-b border-gray-700">
                <SortableTh label="Имя" sortKey="name" sort={sort} onSort={onSort} width="w-[22%]" />
                <SortableTh label="Статус" sortKey="cohort_status" sort={sort} onSort={onSort} width="w-[9%]" />
                <SortableTh label="Курсы" sortKey="courses_count" sort={sort} onSort={onSort} align="right" width="w-[8%]" />
                <SortableTh label="Сертификаты" sortKey="certificates" sort={sort} onSort={onSort} align="right" width="w-[11%]" />
                <SortableTh label="Решения" sortKey="submissions_count" sort={sort} onSort={onSort} align="right" width="w-[13%]" />
                <SortableTh label="Опубликованные" sortKey="published_solutions" sort={sort} onSort={onSort} align="right" width="w-[12%]" />
                <SortableTh label="Комментарии" sortKey="comments_count" sort={sort} onSort={onSort} align="right" width="w-[11%]" />
                <SortableTh label="Активность" sortKey="last_activity" sort={sort} onSort={onSort} align="right" width="w-[14%]" />
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <StudentRow key={s.student_id} student={s} />
              ))}
              {students.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-gray-500 text-sm">
                    Нет данных о студентах
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination page={safePage} totalPages={totalPages} setPage={setPage} />
      </div>
    </div>
  );
}
