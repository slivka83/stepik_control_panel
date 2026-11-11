import { useState } from 'react';
import { useTabState } from '../hooks/useTabState';
import { useTabSorts } from '../hooks/useTabSorts';
import { useServerTable } from '../hooks/useServerTable';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';
import { makeMonthsTick } from '../utils/monthWindow';
import {
  CHART_METRICS,
  COMMENTS_LIST_COLUMNS,
  LIST_SORT_INIT,
  LIST_TABS,
  SORT_INIT,
  TAB_COLUMNS,
  TABS,
} from './comments/columns';

export default function Comments() {
  const { data, error, refresh, selectedCourseIds } = useSync();
  const [activeTab, handleTabChange] = useTabState();
  const { sorts, onSort } = useTabSorts(TAB_COLUMNS, SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('likes_dislikes');

  const isListTab = LIST_TABS.has(activeTab);
  const list = useServerTable({
    endpoint: '/dashboard/comments/list',
    columns: COMMENTS_LIST_COLUMNS,
    initialSort: LIST_SORT_INIT,
    resultKey: 'comments',
    enabled: isListTab,
    resetKey: `${activeTab}|${JSON.stringify(selectedCourseIds)}`,
    extraParams: { type: activeTab },
    resetPageOnSync: true,
  });

  const comments = data.comments || {};
  const months = comments.months || [];
  const years = comments.years || [];
  const byCourse = comments.by_course || [];
  const totals = comments.totals || {};

  const bannerError = error || list.error;
  const retry = () => {
    if (error) refresh();
    if (isListTab) list.refetch();
  };

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

            {isListTab && (
              <DataTable
                columns={COMMENTS_LIST_COLUMNS}
                rows={list.rows}
                initialSort={LIST_SORT_INIT}
                sort={list.sort}
                onSort={list.onSort}
                page={list.page}
                setPage={list.setPage}
                rowsPerPage={list.rowsPerPage}
                tableRef={list.tableRef}
                totalPages={list.totalPages}
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
