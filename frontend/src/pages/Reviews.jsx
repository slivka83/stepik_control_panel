import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';
import { parseMonthLabel, makeMonthsTick } from '../utils/monthWindow';
import { yearMonthLabel, getRatingColor } from '../utils/format';
import { STEPIK_URLS } from '../constants.jsx';

const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
];

const CHART_METRICS = {
  total: {
    label: 'Отзывы',
    format: 'count',
    bars: [{ dataKey: 'total', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Отзывы', value: row.total, color: '#38bdf8' }],
  },
  students: {
    label: 'Студенты',
    format: 'count',
    bars: [{ dataKey: 'students', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Студенты', value: row.students, color: '#38bdf8' }],
  },
  avg_score: {
    label: 'Средняя оценка',
    format: 'rating',
    bars: [{ dataKey: 'avg_score', color: '#4ade80' }],
    tooltip: (row) => [{ label: 'Средняя оценка', value: row.avg_score, color: '#4ade80' }],
  },
};

const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

function monthComposite(m) {
  const p = parseMonthLabel(m.month);
  return p ? p.year * 100 + p.month : 0;
}

const num = (row, key) => <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{row[key] || 0}</td>;
const scoreCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1">
    {row.avg_score ? (
      <span className="font-bold" style={{ color: getRatingColor(row.avg_score) }}>
        {row.avg_score.toFixed(2)}
      </span>
    ) : (
      <span className="text-gray-500">—</span>
    )}
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
    width: 'w-[18%]',
    numeric: true,
    render: (m) => num(m, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[18%]', numeric: true, render: (m) => num(m, 'total') },
  {
    key: 'avg_score',
    label: 'Средняя оценка',
    align: 'right',
    width: 'w-[42%]',
    numeric: true,
    render: (m) => scoreCell(m),
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
    width: 'w-[18%]',
    numeric: true,
    render: (m) => num(m, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[18%]', numeric: true, render: (m) => num(m, 'total') },
  {
    key: 'avg_score',
    label: 'Средняя оценка',
    align: 'right',
    width: 'w-[42%]',
    numeric: true,
    render: (m) => scoreCell(m),
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
            title={c.title}
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
    width: 'w-[17%]',
    numeric: true,
    render: (c) => num(c, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[17%]', numeric: true, render: (c) => num(c, 'total') },
  {
    key: 'avg_score',
    label: 'Средняя оценка',
    align: 'right',
    width: 'w-[36%]',
    numeric: true,
    render: (c) => scoreCell(c),
  },
];

const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
};

export default function Reviews() {
  const { data, error, refresh } = useSync();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const [sorts, setSorts] = useState(SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('total');

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

  const stats = data.reviewsStats || {};
  const months = stats.months || [];
  const years = stats.years || [];
  const byCourse = stats.by_course || [];
  const totals = stats.totals || {};

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        <KpiCard title="Всего отзывов" value={totals.reviews || 0} color="white" />
        <KpiCard title="Студенты" value={totals.students || 0} color="white" />
        <KpiCard title="Средняя оценка" value={totals.avg_score || 0} ratingColor fractionDigits={2} />
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
                emptyText="Нет данных"
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
                emptyText="Нет данных"
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
                emptyText="Нет данных"
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
