import { useMemo, useState } from 'react';
import { useTabState } from '../hooks/useTabState';
import { useTabSorts } from '../hooks/useTabSorts';
import { useSync } from '../contexts/SyncContext';
import { makeMonthsTick } from '../utils/monthWindow';
import { buildDailyStats, chartCommission } from '../utils/financials';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';
import {
  CHARTABLE_TABS,
  CHART_METRICS,
  DAYS_PERIOD,
  DAYS_TICK,
  MONTHS_PERIOD,
  SORT_INIT,
  TAB_COLUMNS,
  TABS,
} from './financials/columns';

export default function Financials() {
  const { data, error, refresh } = useSync();
  const financials = data.financials;
  const [activeTab, handleTabChange] = useTabState();
  const { sorts, onSort } = useTabSorts(TAB_COLUMNS, SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('turnover_income');

  const { summary, months, years, courses, promos, utms, recent_payments } = financials || {};
  const dailyRows = useMemo(() => buildDailyStats(recent_payments), [recent_payments]);
  const chartTab = CHARTABLE_TABS.includes(activeTab) ? activeTab : null;
  const chartRows = useMemo(() => {
    const base = chartTab === 'months' ? months || [] : dailyRows;
    return base.map((r) => ({ ...r, commission: chartCommission(r) }));
  }, [chartTab, months, dailyRows]);
  const chartXKey = chartTab === 'months' ? 'month' : 'day';
  const chartXTick = chartTab === 'months' ? makeMonthsTick(chartRows) : DAYS_TICK;
  const chartPeriodLabel = chartTab === 'months' ? MONTHS_PERIOD : DAYS_PERIOD;

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        <KpiCard title="Оборот" value={summary?.total_turnover || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Доход" value={summary?.total_income || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Возвраты" value={summary?.total_refunds || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Покупок" value={summary?.total_payments || 0} color="white" />
      </div>

      <div className="flex flex-col flex-1 min-h-0">
        <div className="flex items-center justify-between gap-3 shrink-0 flex-wrap">
          <Tabs items={TABS} active={activeTab} onChange={handleTabChange} />

          <ChartToggle
            visible={!!chartTab}
            viewMode={viewMode}
            onToggle={() => setViewMode(viewMode === 'chart' ? 'table' : 'chart')}
            metric={chartMetric}
            onMetricChange={setChartMetric}
            metrics={CHART_METRICS}
          />
        </div>

        {viewMode === 'chart' && chartTab ? (
          <MetricBarChart
            rows={chartRows}
            xKey={chartXKey}
            metric={chartMetric}
            metrics={CHART_METRICS}
            xTick={chartXTick}
            periodLabel={chartPeriodLabel}
          />
        ) : (
          <>
            {activeTab === 'months' && (
              <DataTable
                columns={TAB_COLUMNS.months}
                rows={months || []}
                initialSort={SORT_INIT.months}
                sort={sorts.months}
                onSort={onSort('months')}
                rowKey={(m) => `month-${m.year}-${m.month_num}`}
              />
            )}

            {activeTab === 'years' && (
              <DataTable
                columns={TAB_COLUMNS.years}
                rows={years || []}
                initialSort={SORT_INIT.years}
                sort={sorts.years}
                onSort={onSort('years')}
                rowKey={(m) => `year-${m.year}`}
              />
            )}

            {activeTab === 'days' && (
              <DataTable
                columns={TAB_COLUMNS.days}
                rows={dailyRows}
                initialSort={SORT_INIT.days}
                sort={sorts.days}
                onSort={onSort('days')}
                rowKey={(d) => `day-${d.day}`}
              />
            )}

            {activeTab === 'courses' && (
              <DataTable
                columns={TAB_COLUMNS.courses}
                rows={courses || []}
                initialSort={SORT_INIT.courses}
                sort={sorts.courses}
                onSort={onSort('courses')}
                rowKey={(c) => `course-${c.course_id}`}
              />
            )}

            {activeTab === 'promo' && (
              <DataTable
                columns={TAB_COLUMNS.promo}
                rows={promos || []}
                initialSort={SORT_INIT.promo}
                sort={sorts.promo}
                onSort={onSort('promo')}
                rowKey={(p) => `promo-${p.promo_code}`}
              />
            )}

            {activeTab === 'utms' && (
              <DataTable
                columns={TAB_COLUMNS.utms}
                rows={utms || []}
                initialSort={SORT_INIT.utms}
                sort={sorts.utms}
                onSort={onSort('utms')}
                rowKey={(u) => `utm-${u.utm_source}`}
              />
            )}

            {activeTab === 'recent' && (
              <DataTable
                columns={TAB_COLUMNS.recent}
                rows={recent_payments || []}
                initialSort={SORT_INIT.recent}
                sort={sorts.recent}
                onSort={onSort('recent')}
                rowKey={(p) => `payment-${p.id}`}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
