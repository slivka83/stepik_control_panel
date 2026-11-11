import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import StudentsBar from '../components/StudentsBar';
import DataTable from '../components/DataTable';
import { useServerTable } from '../hooks/useServerTable';
import { COHORT_COLORS } from '../constants.jsx';
import { fmtDate } from '../utils/format';

const cohortHex = (status) => COHORT_COLORS[String(status).toLowerCase()] || '#6b7280';

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
            backgroundColor: `${cohortHex(s.cohort_status)}20`,
            color: cohortHex(s.cohort_status),
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

const INITIAL_SORT = { key: 'last_activity', dir: 'desc' };

export default function Students() {
  const { data, error: syncError, refresh, selectedCourseIds } = useSync();
  const cohorts = data.cohorts;
  const table = useServerTable({
    endpoint: '/dashboard/students',
    columns: STUDENT_COLUMNS,
    initialSort: INITIAL_SORT,
    resultKey: 'students',
    resetKey: JSON.stringify(selectedCourseIds),
  });

  const bannerError = table.error || syncError;
  const retry = () => {
    if (syncError) refresh();
    table.refetch();
  };

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {bannerError && <ErrorBanner message={bannerError} onRetry={retry} />}

      <StudentsBar data={cohorts} />

      <DataTable
        columns={STUDENT_COLUMNS}
        rows={table.rows}
        initialSort={INITIAL_SORT}
        sort={table.sort}
        onSort={table.onSort}
        page={table.page}
        setPage={table.setPage}
        rowsPerPage={table.rowsPerPage}
        tableRef={table.tableRef}
        totalPages={table.totalPages}
        rowKey={(s) => s.student_id}
        emptyText="Нет данных о студентах"
        panelClassName="glass-panel p-4 flex-1 flex flex-col min-h-0 overflow-hidden"
      />
    </div>
  );
}
