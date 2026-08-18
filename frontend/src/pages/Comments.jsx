import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import DataTable, { useRowsPerPage, useSortState } from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';
import { parseMonthLabel, makeMonthsTick } from '../utils/monthWindow';
import { yearMonthLabel, fmtDate } from '../utils/format';
import { STEPIK_URLS } from '../constants.jsx';
import api from '../api';

const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'unanswered', label: 'Не отвеченные' },
  { key: 'disliked', label: 'Дизлайки' },
];

const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

const LIST_SORT_INIT = { key: 'time', dir: 'desc' };

const LIST_TABS = new Set(['unanswered', 'disliked']);

const CHART_METRICS = {
  likes_dislikes: {
    label: 'Лайки / Дизлайки',
    format: 'count',
    bars: [
      { dataKey: 'likes', color: '#4ade80' },
      { dataKey: 'dislikes', color: '#f43f5e' },
    ],
    tooltip: (row) => [
      { label: 'Лайки', value: row.likes, color: '#4ade80' },
      { label: 'Дизлайки', value: row.dislikes, color: '#f43f5e' },
      { label: 'Ответы', value: row.replies },
      { label: 'Всего', value: row.total },
    ],
  },
  replies: {
    label: 'Ответы',
    format: 'count',
    bars: [{ dataKey: 'replies', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Ответы', value: row.replies, color: '#38bdf8' }],
  },
  total: {
    label: 'Всего',
    format: 'count',
    bars: [{ dataKey: 'total', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Всего', value: row.total, color: '#38bdf8' }],
  },
};

function monthComposite(m) {
  const p = parseMonthLabel(m.month);
  return p ? p.year * 100 + p.month : 0;
}

const num = (row, key) => <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{row[key] || 0}</td>;
const likesCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: '#4ade80' }}>
    {row.likes || 0}
  </td>
);
const dislikesCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: '#f43f5e' }}>
    {row.dislikes || 0}
  </td>
);

const commentTextCell = (c) => (
  <td className="text-left pl-1 text-xs truncate">
    <span className="text-gray-300 font-mono text-xs" title={c.text || ''}>
      {c.text || '—'}
    </span>
  </td>
);

const stepCell = (c) => (
  <td className="text-left pl-1 text-xs">
    {c.lesson_id && c.step_number ? (
      <a
        href={STEPIK_URLS.comment(c.lesson_id, c.comment_id)}
        target="_blank"
        rel="noopener noreferrer"
        title={
          c.module_title && c.lesson_title ? `${c.module_title} — ${c.lesson_title}` : `Комментарий ${c.comment_id}`
        }
        className="text-cyber-blue font-mono text-xs hover:underline"
      >
        {c.module_number && c.lesson_number ? `${c.module_number}.${c.lesson_number}-${c.step_number}` : c.step_number}
      </a>
    ) : (
      <span className="text-cyber-blue font-mono text-xs" title={`Комментарий ${c.comment_id}`}>
        {c.comment_id || '—'}
      </span>
    )}
  </td>
);

const studentCell = (c) => (
  <td className="text-left pl-1 text-xs truncate">
    <span className="text-gray-300 font-mono text-xs">{c.user_name || '—'}</span>
  </td>
);

const courseCell = (c) => (
  <td className="text-left pl-1 text-xs truncate">
    {c.stepik_course_id ? (
      <a
        href={STEPIK_URLS.course(c.stepik_course_id)}
        target="_blank"
        rel="noopener noreferrer"
        className="text-cyber-blue font-mono text-xs hover:underline truncate block"
        title={c.course_title}
      >
        {c.course_title}
      </a>
    ) : (
      <span className="text-gray-300 font-mono text-xs">{c.course_title || '—'}</span>
    )}
  </td>
);

const dateCell = (c) => (
  <td className="text-right font-mono text-xs text-gray-400 pl-1 pr-1 whitespace-nowrap">
    {c.time ? fmtDate(c.time) : '—'}
  </td>
);

const MONTH_COLUMNS = [
  {
    key: 'month',
    label: 'Месяц',
    width: 'w-[22%]',
    numeric: true,
    getValue: monthComposite,
    render: (m) => <td className="text-gray-300 font-mono text-xs pl-1 truncate">{yearMonthLabel(m.month)}</td>,
  },
  {
    key: 'students',
    label: 'Студенты',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (m) => num(m, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[14%]', numeric: true, render: (m) => num(m, 'total') },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[16%]', numeric: true, render: (m) => likesCell(m) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => dislikesCell(m),
  },
  {
    key: 'replies',
    label: 'Ответы',
    align: 'right',
    width: 'w-[18%]',
    numeric: true,
    render: (m) => num(m, 'replies'),
  },
];

const YEARS_COLUMNS = [
  {
    key: 'year',
    label: 'Год',
    width: 'w-[22%]',
    numeric: true,
    render: (m) => <td className="text-gray-300 font-mono text-xs pl-1 truncate">{m.year}</td>,
  },
  {
    key: 'students',
    label: 'Студенты',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => num(m, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[16%]', numeric: true, render: (m) => num(m, 'total') },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[15%]', numeric: true, render: (m) => likesCell(m) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[15%]',
    numeric: true,
    render: (m) => dislikesCell(m),
  },
  {
    key: 'replies',
    label: 'Ответы',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => num(m, 'replies'),
  },
];

const COURSES_COLUMNS = [
  {
    key: 'title',
    label: 'Курс',
    width: 'w-[30%]',
    render: (c) => (
      <td className="text-left pl-1 text-xs truncate">
        {c.stepik_course_id ? (
          <a
            href={STEPIK_URLS.course(c.stepik_course_id)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-cyber-blue font-mono text-xs hover:underline truncate block"
          >
            {c.title}
          </a>
        ) : (
          <span className="text-gray-300 font-mono text-xs">{c.title}</span>
        )}
      </td>
    ),
  },
  {
    key: 'students',
    label: 'Студенты',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (c) => num(c, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[14%]', numeric: true, render: (c) => num(c, 'total') },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[14%]', numeric: true, render: (c) => likesCell(c) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (c) => dislikesCell(c),
  },
  {
    key: 'replies',
    label: 'Ответы',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (c) => num(c, 'replies'),
  },
];

const COMMENTS_LIST_COLUMNS = [
  {
    key: 'time',
    label: 'Дата',
    width: 'w-[12%]',
    nullLast: true,
    naturalDir: 'asc',
    render: dateCell,
  },
  {
    key: 'student',
    label: 'Студент',
    width: 'w-[16%]',
    getValue: (c) => c.user_name || '',
    render: studentCell,
  },
  {
    key: 'course',
    label: 'Курс',
    width: 'w-[16%]',
    getValue: (c) => c.course_title || '',
    render: courseCell,
  },
  {
    key: 'text',
    label: 'Комментарий',
    width: 'w-[26%]',
    getValue: (c) => c.text || '',
    render: commentTextCell,
  },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[7%]', numeric: true, render: (c) => likesCell(c) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[7%]',
    numeric: true,
    render: (c) => dislikesCell(c),
  },
  { key: 'replies', label: 'Ответы', align: 'right', width: 'w-[7%]', numeric: true, render: (c) => num(c, 'replies') },
  {
    key: 'step',
    label: 'Шаг',
    width: 'w-[9%]',
    numeric: true,
    getValue: (c) => c.step_number,
    render: stepCell,
  },
];

const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
  unanswered: COMMENTS_LIST_COLUMNS,
  disliked: COMMENTS_LIST_COLUMNS,
};

export default function Comments() {
  const { data, error, refresh, selectedCourseIds, syncStatus } = useSync();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const [sorts, setSorts] = useState(SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('likes_dislikes');

  const [listRows, setListRows] = useState([]);
  const [listTotal, setListTotal] = useState(0);
  const [listError, setListError] = useState(null);
  const [listPage, setListPage] = useState(1);
  const { tableRef, rowsPerPage } = useRowsPerPage();
  const { sort: listSort, onSort: listOnSort } = useSortState(COMMENTS_LIST_COLUMNS, LIST_SORT_INIT);
  const listReqIdRef = useRef(0);
  const firstRenderRef = useRef(true);
  const prevLastSyncRef = useRef(null);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const onSort = (tab) => (key) => {
    setSorts((prev) => {
      const cur = prev[tab];
      const cfg = TAB_COLUMNS[tab].find((c) => c.key === key);
      const next =
        cur.key === key
          ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: cfg?.numeric ? 'desc' : 'asc' };
      return { ...prev, [tab]: next };
    });
  };

  const comments = data.comments || {};
  const months = comments.months || [];
  const years = comments.years || [];
  const byCourse = comments.by_course || [];
  const totals = comments.totals || {};

  const listTotalPages = Math.max(1, Math.ceil(listTotal / rowsPerPage));
  const safeListPage = Math.min(listPage, listTotalPages);

  const fetchList = useCallback(async () => {
    const id = ++listReqIdRef.current;
    const params = {};
    if (selectedCourseIds !== null) params.course_ids = selectedCourseIds.join(',');
    try {
      const res = await api.get('/dashboard/comments/list', {
        params: {
          type: activeTab,
          skip: (safeListPage - 1) * rowsPerPage,
          limit: rowsPerPage,
          sort: listSort.key,
          order: listSort.dir,
          ...params,
        },
      });
      if (listReqIdRef.current !== id) return;
      setListRows(res.data.comments);
      setListTotal(res.data.total);
      setListError(null);
    } catch (e) {
      if (listReqIdRef.current !== id) return;
      setListError(e.message);
    }
  }, [activeTab, safeListPage, rowsPerPage, listSort.key, listSort.dir, selectedCourseIds]);

  useEffect(() => {
    if (!LIST_TABS.has(activeTab)) return;
    fetchList();
  }, [activeTab, fetchList]);

  useEffect(() => {
    if (firstRenderRef.current) {
      firstRenderRef.current = false;
      return;
    }
    if (LIST_TABS.has(activeTab)) setListPage(1);
  }, [selectedCourseIds, listSort.key, listSort.dir, activeTab]);

  useEffect(() => {
    if (
      LIST_TABS.has(activeTab) &&
      prevLastSyncRef.current !== null &&
      syncStatus.last_sync !== prevLastSyncRef.current
    ) {
      fetchList();
    }
    prevLastSyncRef.current = syncStatus.last_sync;
  }, [syncStatus.last_sync, activeTab, fetchList]);

  useEffect(() => {
    if (LIST_TABS.has(activeTab) && listPage > listTotalPages) setListPage(listTotalPages);
  }, [listPage, listTotalPages, activeTab]);

  const bannerError = error || listError;
  const retry = () => {
    if (error) refresh();
    if (LIST_TABS.has(activeTab)) fetchList();
  };

  const isListTab = LIST_TABS.has(activeTab);

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {bannerError && <ErrorBanner message={bannerError} onRetry={retry} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        <KpiCard title="Всего комментариев" value={totals.comments || 0} color="white" />
        <KpiCard title="Студенты" value={totals.students || 0} color="white" />
        <KpiCard title="Лайки" value={totals.likes || 0} color="neon-green" />
        <KpiCard title="Дизлайки" value={totals.dislikes || 0} color="crimson-alert" />
      </div>

      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex items-center justify-between gap-3 shrink-0 flex-wrap">
          <Tabs items={TABS} active={activeTab} onChange={handleTabChange} />

          <ChartToggle
            visible={activeTab === 'months'}
            viewMode={viewMode}
            onToggle={() => setViewMode(viewMode === 'chart' ? 'table' : 'chart')}
            metric={chartMetric}
            onMetricChange={setChartMetric}
            metrics={CHART_METRICS}
          />
        </div>

        {viewMode === 'chart' && activeTab === 'months' ? (
          <MetricBarChart
            rows={months}
            metric={chartMetric}
            metrics={CHART_METRICS}
            xTick={makeMonthsTick(months)}
            periodLabel={(m) => m.month}
          />
        ) : (
          <>
            {activeTab === 'months' && (
              <DataTable
                columns={MONTH_COLUMNS}
                rows={months}
                initialSort={SORT_INIT.months}
                sort={sorts.months}
                onSort={onSort('months')}
                rowKey={(m) => m.month}
              />
            )}

            {activeTab === 'years' && (
              <DataTable
                columns={YEARS_COLUMNS}
                rows={years}
                initialSort={SORT_INIT.years}
                sort={sorts.years}
                onSort={onSort('years')}
                rowKey={(m) => m.year}
              />
            )}

            {activeTab === 'courses' && (
              <DataTable
                columns={COURSES_COLUMNS}
                rows={byCourse}
                initialSort={SORT_INIT.courses}
                sort={sorts.courses}
                onSort={onSort('courses')}
                rowKey={(c) => c.course_id}
              />
            )}

            {isListTab && (
              <DataTable
                columns={COMMENTS_LIST_COLUMNS}
                rows={listRows}
                initialSort={LIST_SORT_INIT}
                sort={listSort}
                onSort={listOnSort}
                page={listPage}
                setPage={setListPage}
                rowsPerPage={rowsPerPage}
                tableRef={tableRef}
                totalPages={listTotalPages}
                rowKey={(c) => c.comment_id}
                emptyText="Нет комментариев"
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
