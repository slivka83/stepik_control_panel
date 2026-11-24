import { useState, useEffect } from 'react';
import { useTabState } from '../hooks/useTabState';
import { useTabSorts } from '../hooks/useTabSorts';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';
import { makeMonthsTick } from '../utils/monthWindow';
import api from '../api';
import {
  calcWrong,
  CHART_METRICS,
  SORT_INIT,
  SUCCESS_BAD_PCT,
  SUCCESS_OK_PCT,
  TAB_COLUMNS,
  TABS,
} from './solutions/columns';

const TAB_KEYS = TABS.map((t) => t.key);

export default function Solutions() {
  const { data, error, refresh, selectedCourseIds, syncStatus } = useSync();
  const [activeTab, handleTabChange] = useTabState('months', TAB_KEYS);
  const { sorts, onSort } = useTabSorts(TAB_COLUMNS, SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('correct_wrong');

  const [hardestSteps, setHardestSteps] = useState([]);
  const [hardestLoading, setHardestLoading] = useState(false);
  const [hardestError, setHardestError] = useState(null);

  useEffect(() => {
    if (activeTab !== 'hardest') return undefined;
    let cancelled = false;
    setHardestLoading(true);
    setHardestError(null);
    const params = { limit: 200, min_submissions: 1 };
    if (selectedCourseIds != null) params.course_ids = selectedCourseIds.join(',');
    api
      .get('/dashboard/hardest-steps', { params })
      .then((res) => {
        if (!cancelled) setHardestSteps(res.data.steps || []);
      })
      .catch(() => {
        if (!cancelled) setHardestError('Не удалось загрузить данные');
      })
      .finally(() => {
        if (!cancelled) setHardestLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, selectedCourseIds, syncStatus.last_sync]);

  const submissions = data.submissions || {};
  const months = submissions.months || [];
  const byCourse = submissions.by_course || [];
  const years = submissions.years || [];
  const chartRows = months.map((m) => ({ ...m, wrong: calcWrong(m) }));

  const totalSubmissions = months.reduce((s, m) => s + (m.total || 0), 0);
  const totalCorrect = months.reduce((s, m) => s + (m.correct || 0), 0);
  const totalWrong = totalSubmissions - totalCorrect;
  const totalPublished = months.reduce((s, m) => s + (m.published || 0), 0);
  const publishedTotal = submissions.published_total ?? totalPublished;
  const avgSuccess = totalSubmissions > 0 ? Math.round((totalCorrect / totalSubmissions) * 100) : 0;

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 shrink-0">
        <KpiCard title="Всего решений" value={totalSubmissions} color="white" />
        <KpiCard title="Правильных" value={totalCorrect} color="white" />
        <KpiCard title="Неправильных" value={totalWrong} color="white" />
        <KpiCard title="Опубликованные" value={publishedTotal} color="white" />
        <KpiCard
          title="Успех"
          value={avgSuccess}
          suffix="%"
          color={
            avgSuccess < SUCCESS_BAD_PCT
              ? 'crimson-alert'
              : avgSuccess < SUCCESS_OK_PCT
                ? 'amber-alert'
                : 'neon-green'
          }
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
                columns={TAB_COLUMNS.months}
                rows={months}
                initialSort={SORT_INIT.months}
                sort={sorts.months}
                onSort={onSort('months')}
                rowKey={(m) => m.month}
              />
            )}

            {activeTab === 'years' && (
              <DataTable
                columns={TAB_COLUMNS.years}
                rows={years}
                initialSort={SORT_INIT.years}
                sort={sorts.years}
                onSort={onSort('years')}
                rowKey={(m) => m.year}
              />
            )}

            {activeTab === 'courses' && (
              <DataTable
                columns={TAB_COLUMNS.courses}
                rows={byCourse}
                initialSort={SORT_INIT.courses}
                sort={sorts.courses}
                onSort={onSort('courses')}
                rowKey={(c) => c.course_id}
              />
            )}

            {activeTab === 'hardest' && (
              <DataTable
                columns={TAB_COLUMNS.hardest}
                rows={hardestSteps}
                initialSort={SORT_INIT.hardest}
                sort={sorts.hardest}
                onSort={onSort('hardest')}
                rowKey={(s) => `${s.course_id}-${s.stepik_step_id}`}
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
