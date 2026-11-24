import { useState } from 'react';
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
import { CHART_METRICS, SORT_INIT, TAB_COLUMNS, TABS } from './reviews/columns';

const TAB_KEYS = TABS.map((t) => t.key);

export default function Reviews() {
  const { data, error, refresh } = useSync();
  const [activeTab, handleTabChange] = useTabState('months', TAB_KEYS);
  const { sorts, onSort } = useTabSorts(TAB_COLUMNS, SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('total');

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
        <KpiCard
          title="Средняя оценка"
          value={totals.avg_score || 0}
          ratingColor
          noZero
          fractionDigits={2}
          minimumFractionDigits={2}
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
                columns={TAB_COLUMNS.months}
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
                columns={TAB_COLUMNS.years}
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
                columns={TAB_COLUMNS.courses}
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
