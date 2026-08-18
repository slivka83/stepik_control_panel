import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';
import { parseMonthLabel, makeMonthsTick } from '../utils/monthWindow';
import { yearMonthLabel } from '../utils/format';
import { STEPIK_URLS } from '../constants.jsx';
import api from '../api';

const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'hardest', label: 'Самые сложные' },
];

const CHART_METRICS = {
  correct_wrong: {
    label: 'Правильно / Неверно',
    format: 'count',
    bars: [
      { dataKey: 'correct', color: '#38bdf8' },
      { dataKey: 'wrong', color: '#1a6a9e' },
    ],
    tooltip: (row) => [
      { label: 'Правильно', value: row.correct, color: '#38bdf8' },
      { label: 'Неверно', value: row.wrong, color: '#1a6a9e' },
      { label: 'Опубликованные', value: row.published },
      { label: 'Всего', value: row.total },
    ],
  },
  published: {
    label: 'Опубликованные',
    format: 'count',
    bars: [{ dataKey: 'published', color: '#DB62C4' }],
    tooltip: (row) => [{ label: 'Опубликованные', value: row.published, color: '#DB62C4' }],
  },
  students: {
    label: 'Студенты',
    format: 'count',
    bars: [{ dataKey: 'students', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Студенты', value: row.students, color: '#38bdf8' }],
  },
};

const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
  hardest: { key: 'weighted_success', dir: 'asc' },
};

function successColor(pct) {
  if (pct < 33) return '#f43f5e';
  if (pct < 66) return '#f59e0b';
  return '#4ade80';
}

function calcWrong(m) {
  return (m.total || 0) - (m.correct || 0);
}

function calcPct(m) {
  if (m.success_pct != null) return m.success_pct;
  return m.total > 0 ? ((m.correct || 0) / m.total) * 100 : 0;
}

function monthComposite(m) {
  const p = parseMonthLabel(m.month);
  return p ? p.year * 100 + p.month : 0;
}

const numCell = (value) => (
  <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{value.toLocaleString('ru-RU')}</td>
);
const num = (row, key) => numCell(row[key] || 0);
const successCell = (pct) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: successColor(pct) }}>
    {pct.toFixed(1)}%
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
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[16%]', numeric: true, render: (m) => num(m, 'total') },
  {
    key: 'correct',
    label: 'Правильно',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => num(m, 'correct'),
  },
  {
    key: 'published',
    label: 'Опубликованные',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (m) => num(m, 'published'),
  },
  {
    key: 'wrong',
    label: 'Неверно',
    align: 'right',
    width: 'w-[13%]',
    numeric: true,
    getValue: calcWrong,
    render: (m) => numCell(calcWrong(m)),
  },
  {
    key: 'success',
    label: 'Успех',
    align: 'right',
    width: 'w-[13%]',
    numeric: true,
    getValue: calcPct,
    render: (m) => successCell(calcPct(m)),
  },
];

const YEARS_COLUMNS = [
  {
    key: 'year',
    label: 'Год',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => <td className="text-gray-300 font-mono text-xs pl-1 truncate">{m.year}</td>,
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
  {
    key: 'correct',
    label: 'Правильно',
    align: 'right',
    width: 'w-[17%]',
    numeric: true,
    render: (m) => num(m, 'correct'),
  },
  {
    key: 'published',
    label: 'Опубликованные',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (m) => num(m, 'published'),
  },
  {
    key: 'wrong',
    label: 'Неверно',
    align: 'right',
    width: 'w-[13%]',
    numeric: true,
    getValue: calcWrong,
    render: (m) => numCell(calcWrong(m)),
  },
  {
    key: 'success',
    label: 'Успех',
    align: 'right',
    width: 'w-[12%]',
    numeric: true,
    getValue: calcPct,
    render: (m) => successCell(calcPct(m)),
  },
];

const COURSES_COLUMNS = [
  {
    key: 'title',
    label: 'Курс',
    width: 'w-[24%]',
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
    width: 'w-[12%]',
    numeric: true,
    render: (c) => num(c, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[13%]', numeric: true, render: (c) => num(c, 'total') },
  {
    key: 'correct',
    label: 'Правильно',
    align: 'right',
    width: 'w-[15%]',
    numeric: true,
    render: (c) => num(c, 'correct'),
  },
  {
    key: 'published',
    label: 'Опубликованные',
    align: 'right',
    width: 'w-[13%]',
    numeric: true,
    render: (c) => num(c, 'published'),
  },
  {
    key: 'wrong',
    label: 'Неверно',
    align: 'right',
    width: 'w-[12%]',
    numeric: true,
    getValue: calcWrong,
    render: (c) => numCell(calcWrong(c)),
  },
  {
    key: 'success',
    label: 'Успех',
    align: 'right',
    width: 'w-[11%]',
    numeric: true,
    getValue: calcPct,
    render: (c) => successCell(calcPct(c)),
  },
];

const HARDEST_COLUMNS = [
  {
    key: 'step_id',
    label: 'Шаг',
    width: 'w-[10%]',
    numeric: true,
    getValue: (s) => s.stepik_step_id,
    render: (s) => (
      <td className="text-left pl-1 text-xs">
        {s.lesson_id && s.step_number ? (
          <a
            href={STEPIK_URLS.step(s.lesson_id, s.step_number)}
            target="_blank"
            rel="noopener noreferrer"
            title={
              s.module_title && s.lesson_title
                ? `${s.module_title} — ${s.lesson_title}`
                : `${s.course_title} — шаг ${s.stepik_step_id}`
            }
            className="text-cyber-blue font-mono text-xs hover:underline"
          >
            {s.module_number && s.lesson_number
              ? `${s.module_number}.${s.lesson_number}-${s.step_number}`
              : s.stepik_step_id}
          </a>
        ) : (
          <span className="text-cyber-blue font-mono text-xs" title={`Шаг ${s.stepik_step_id}`}>
            {s.stepik_step_id}
          </span>
        )}
      </td>
    ),
  },
  {
    key: 'title',
    label: 'Курс',
    width: 'w-[30%]',
    getValue: (s) => s.course_title,
    render: (s) => <td className="text-gray-300 font-mono text-xs pl-1 truncate">{s.course_title}</td>,
  },
  {
    key: 'students',
    label: 'Студенты',
    align: 'right',
    width: 'w-[12%]',
    numeric: true,
    render: (s) => num(s, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[12%]', numeric: true, render: (s) => num(s, 'total') },
  {
    key: 'correct',
    label: 'Правильно',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (s) => num(s, 'correct'),
  },
  {
    key: 'wrong',
    label: 'Неверно',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    getValue: calcWrong,
    render: (s) => numCell(calcWrong(s)),
  },
  {
    key: 'success',
    label: 'Успех',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    getValue: (s) => s.success_pct,
    render: (s) => (
      <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: successColor(s.success_pct) }}>
        {s.success_pct}%
      </td>
    ),
  },
  {
    key: 'weighted_success',
    label: 'Взв. успех',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    getValue: (s) => (s.weighted_success_pct != null ? s.weighted_success_pct : s.success_pct),
    render: (s) => {
      const p = s.weighted_success_pct != null ? s.weighted_success_pct : s.success_pct;
      return (
        <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: successColor(p) }}>
          {p}%
        </td>
      );
    },
  },
];

const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
  hardest: HARDEST_COLUMNS,
};

export default function Solutions() {
  const { data, error, refresh, selectedCourseIds } = useSync();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const [sorts, setSorts] = useState(SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('correct_wrong');

  const [hardestSteps, setHardestSteps] = useState([]);
  const [hardestLoading, setHardestLoading] = useState(false);
  const [hardestError, setHardestError] = useState(null);

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

  useEffect(() => {
    if (activeTab !== 'hardest') return;
    setHardestLoading(true);
    setHardestError(null);
    const params = { limit: 200, min_submissions: 1 };
    if (selectedCourseIds) params.course_ids = selectedCourseIds.join(',');
    api
      .get('/dashboard/hardest-steps', { params })
      .then((res) => setHardestSteps(res.data.steps || []))
      .catch(() => setHardestError('Не удалось загрузить данные'))
      .finally(() => setHardestLoading(false));
  }, [activeTab, selectedCourseIds]);

  const submissions = data.submissions || {};
  const months = submissions.months || [];
  const byCourse = submissions.by_course || [];
  const years = submissions.years || [];
  const chartRows = months.map((m) => ({ ...m, wrong: calcWrong(m) }));

  const totalSubmissions = months.reduce((s, m) => s + (m.total || 0), 0);
  const totalCorrect = months.reduce((s, m) => s + (m.correct || 0), 0);
  const totalWrong = totalSubmissions - totalCorrect;
  const totalPublished = months.reduce((s, m) => s + (m.published || 0), 0);
  const avgSuccess = totalSubmissions > 0 ? Math.round((totalCorrect / totalSubmissions) * 100) : 0;

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 shrink-0">
        <KpiCard title="Всего решений" value={totalSubmissions} color="white" />
        <KpiCard title="Правильных" value={totalCorrect} color="white" />
        <KpiCard title="Неправильных" value={totalWrong} color="white" />
        <KpiCard title="Опубликованные" value={totalPublished} color="white" />
        <KpiCard
          title="Успех"
          value={avgSuccess}
          suffix="%"
          color={avgSuccess < 33 ? 'crimson-alert' : avgSuccess < 66 ? 'amber-alert' : 'neon-green'}
        />
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
            rows={chartRows}
            metric={chartMetric}
            metrics={CHART_METRICS}
            xTick={makeMonthsTick(chartRows)}
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

            {activeTab === 'hardest' && (
              <DataTable
                columns={HARDEST_COLUMNS}
                rows={hardestSteps}
                initialSort={SORT_INIT.hardest}
                sort={sorts.hardest}
                onSort={onSort('hardest')}
                rowKey={(s) => s.stepik_step_id}
                loading={hardestLoading}
                error={hardestError}
                emptyText="Нет данных"
                emptyCentered
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
