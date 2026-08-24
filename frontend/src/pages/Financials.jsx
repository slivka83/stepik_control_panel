import { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import { formatCurrency } from '../utils/formatNumber';
import { yearMonthLabel } from '../utils/format';
import { makeMonthsTick } from '../utils/monthWindow';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import MetricBarChart from '../components/MetricBarChart';
import ChartToggle from '../components/ChartToggle';

const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'days', label: 'По дням' },
  { key: 'courses', label: 'По курсам' },
  { key: 'promo', label: 'По промокодам' },
  { key: 'utms', label: 'По UTM' },
  { key: 'recent', label: 'Последние операции' },
];

const CHARTABLE_TABS = ['months', 'days'];

const CHART_METRICS = {
  turnover_income: {
    label: 'Оборот / Доход',
    format: 'money',
    bars: [
      { dataKey: 'income', color: '#4ade80' },
      { dataKey: 'commission', color: '#4ade80', fillOpacity: 0.35 },
    ],
    tooltip: (row) => [
      { label: 'Доход', value: row.income, color: '#4ade80' },
      { label: 'Оборот', value: row.turnover, color: '#4ade80', dim: true },
    ],
  },
  payments: {
    label: 'Покупок',
    format: 'count',
    bars: [{ dataKey: 'payments_count', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Покупок', value: row.payments_count, color: '#38bdf8' }],
  },
  refunds: {
    label: 'Возвраты',
    format: 'money',
    bars: [{ dataKey: 'refunds', color: '#f43f5e' }],
    tooltip: (row) => [{ label: 'Возвраты', value: row.refunds, color: '#f43f5e' }],
  },
};

const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  days: { key: 'day', dir: 'desc' },
  courses: { key: 'income', dir: 'desc' },
  promo: { key: 'income', dir: 'desc' },
  utms: { key: 'income', dir: 'desc' },
  recent: { key: 'time', dir: 'desc' },
};

function monthCompositeValue(m) {
  if (m.year != null && m.month_num != null) return m.year * 100 + m.month_num;
  return 0;
}

function formatUtmTooltip(raw) {
  const utm = raw?.last_course_click_utm;
  if (!utm || typeof utm !== 'object') return '';
  return Object.entries(utm)
    .map(([k, v]) => `${k}: ${v ?? ''}`)
    .join('\n');
}

const moneyCell = (key, className) => (row) => (
  <td className={`text-right font-mono text-xs pl-1 pr-1 ${className}`}>{formatCurrency(row[key])}</td>
);
const grayMoneyCell = moneyCell('turnover', 'text-gray-300');
const greenMoneyCell = moneyCell('income', 'text-neon-green');
const refundsCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1 text-crimson-alert">
    {row.refunds > 0 ? `-${formatCurrency(row.refunds)}` : '—'}
  </td>
);
const paymentsCell = (row) => <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{row.payments}</td>;
const lastUsedCell = (row) => (
  <td className="text-right text-gray-400 text-xs pl-1 pr-1 truncate">
    {row.last_used ? new Date(row.last_used).toLocaleDateString('ru-RU') : '—'}
  </td>
);
const commissionOf = (p) => {
  const payment = Number(p.payment_amount);
  const income = Number(p.amount);
  if (!Number.isFinite(payment) || payment <= 0) return null;
  const fee = payment - Math.abs(Number.isFinite(income) ? income : 0);
  return { pct: Math.round((fee / payment) * 100), amount: fee };
};

const MONTHS_COLUMNS = [
  {
    key: 'month',
    label: 'Месяц',
    width: 'w-[28%]',
    numeric: true,
    getValue: monthCompositeValue,
    render: (m) => <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{yearMonthLabel(m.month)}</td>,
  },
  {
    key: 'payments_count',
    label: 'Покупок',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{m.payments_count}</td>,
  },
  { key: 'turnover', label: 'Оборот', align: 'right', width: 'w-[22%]', numeric: true, render: grayMoneyCell },
  { key: 'income', label: 'Доход', align: 'right', width: 'w-[20%]', numeric: true, render: greenMoneyCell },
  { key: 'refunds', label: 'Возвраты', align: 'right', width: 'w-[14%]', numeric: true, render: refundsCell },
];

const YEARS_COLUMNS = [
  {
    key: 'year',
    label: 'Год',
    width: 'w-[28%]',
    numeric: true,
    render: (m) => <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{m.year}</td>,
  },
  {
    key: 'payments_count',
    label: 'Покупок',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{m.payments_count}</td>,
  },
  { key: 'turnover', label: 'Оборот', align: 'right', width: 'w-[22%]', numeric: true, render: grayMoneyCell },
  { key: 'income', label: 'Доход', align: 'right', width: 'w-[20%]', numeric: true, render: greenMoneyCell },
  { key: 'refunds', label: 'Возвраты', align: 'right', width: 'w-[14%]', numeric: true, render: refundsCell },
];

function dayCompositeValue(d) {
  const parsed = Date.parse(d.day);
  return Number.isNaN(parsed) ? 0 : parsed;
}

const DAYS_COLUMNS = [
  {
    key: 'day',
    label: 'Дата',
    width: 'w-[28%]',
    numeric: true,
    getValue: dayCompositeValue,
    render: (d) => (
      <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{d.day.split('-').reverse().join('.')}</td>
    ),
  },
  {
    key: 'payments_count',
    label: 'Покупок',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (d) => <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{d.payments_count}</td>,
  },
  { key: 'turnover', label: 'Оборот', align: 'right', width: 'w-[22%]', numeric: true, render: grayMoneyCell },
  { key: 'income', label: 'Доход', align: 'right', width: 'w-[20%]', numeric: true, render: greenMoneyCell },
  { key: 'refunds', label: 'Возвраты', align: 'right', width: 'w-[14%]', numeric: true, render: refundsCell },
];

// Aggregate recent payments by the viewer's LOCAL calendar day, mirroring the
// date logic used by the "Последние операции" tab (new Date(p.time)). This
// guarantees the "today" row matches what the recent-operations tab shows.
export function buildDailyStats(recent, daysBack = 30) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const buckets = {};
  for (const p of recent || []) {
    const t = new Date(p.time);
    if (Number.isNaN(t.getTime())) continue;
    const d = new Date(t.getFullYear(), t.getMonth(), t.getDate());
    if (d > today) continue;
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const b =
      buckets[key] ||
      (buckets[key] = {
        day: key,
        payments_count: 0,
        turnover: 0,
        income: 0,
        refunds: 0,
        refunds_count: 0,
      });
    b.payments_count += 1;
    const status = p.status || '';
    const amount = parseFloat(p.amount) || 0;
    const paymentAmount = parseFloat(p.payment_amount) || 0;
    if (status === 'refunded') {
      b.refunds += Math.abs(amount);
      b.refunds_count += 1;
      b.turnover -= paymentAmount;
      b.income += amount;
    } else {
      b.turnover += paymentAmount;
      b.income += amount;
    }
  }
  const out = [];
  const start = new Date(today);
  start.setDate(start.getDate() - (daysBack - 1));
  for (let i = 0; i < daysBack; i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    out.push(
      buckets[key] || {
        day: key,
        payments_count: 0,
        turnover: 0,
        income: 0,
        refunds: 0,
        refunds_count: 0,
      },
    );
  }
  out.sort((a, b) => (a.day < b.day ? 1 : -1));
  return out;
}

const COURSES_COLUMNS = [
  {
    key: 'title',
    label: 'Курс',
    width: 'w-[32%]',
    render: (c) => (
      <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate" title={c.title}>
        <a
          href={`https://stepik.org/course/${c.course_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyber-blue hover:underline"
        >
          {c.title}
        </a>
      </td>
    ),
  },
  { key: 'payments', label: 'Покупок', align: 'right', width: 'w-[12%]', numeric: true, render: paymentsCell },
  { key: 'turnover', label: 'Оборот', align: 'right', width: 'w-[14%]', numeric: true, render: grayMoneyCell },
  { key: 'income', label: 'Доход', align: 'right', width: 'w-[14%]', numeric: true, render: greenMoneyCell },
  { key: 'refunds', label: 'Возвраты', align: 'right', width: 'w-[14%]', numeric: true, render: refundsCell },
  {
    key: 'price',
    label: 'Стоимость',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    nullLast: true,
    render: (c) => (
      <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">
        {c.price ? formatCurrency(c.price) : '—'}
      </td>
    ),
  },
];

const PROMOS_COLUMNS = [
  {
    key: 'promo_code',
    label: 'Промокод',
    width: 'w-[18%]',
    render: (p) => <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{p.promo_code}</td>,
  },
  { key: 'payments', label: 'Покупок', align: 'right', width: 'w-[12%]', numeric: true, render: paymentsCell },
  { key: 'turnover', label: 'Оборот', align: 'right', width: 'w-[18%]', numeric: true, render: grayMoneyCell },
  { key: 'income', label: 'Доход', align: 'right', width: 'w-[16%]', numeric: true, render: greenMoneyCell },
  { key: 'refunds', label: 'Возвраты', align: 'right', width: 'w-[14%]', numeric: true, render: refundsCell },
  {
    key: 'last_used',
    label: 'Последнее применение',
    align: 'right',
    width: 'w-[22%]',
    nullLast: true,
    naturalDir: 'asc',
    render: lastUsedCell,
  },
];

const UTMS_COLUMNS = [
  {
    key: 'utm_source',
    label: 'UTM',
    width: 'w-[18%]',
    render: (u) => <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{u.utm_source}</td>,
  },
  { key: 'payments', label: 'Покупок', align: 'right', width: 'w-[12%]', numeric: true, render: paymentsCell },
  { key: 'turnover', label: 'Оборот', align: 'right', width: 'w-[18%]', numeric: true, render: grayMoneyCell },
  { key: 'income', label: 'Доход', align: 'right', width: 'w-[16%]', numeric: true, render: greenMoneyCell },
  { key: 'refunds', label: 'Возвраты', align: 'right', width: 'w-[14%]', numeric: true, render: refundsCell },
  {
    key: 'last_used',
    label: 'Последнее применение',
    align: 'right',
    width: 'w-[22%]',
    nullLast: true,
    naturalDir: 'asc',
    render: lastUsedCell,
  },
];

const RECENT_COLUMNS = [
  {
    key: 'time',
    label: 'Дата',
    width: 'w-[12%]',
    naturalDir: 'asc',
    render: (p) => (
      <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">
        {`${new Date(p.time).toLocaleDateString('ru-RU')} ${new Date(p.time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`}
      </td>
    ),
  },
  {
    key: 'course',
    label: 'Курс',
    width: 'w-[26%]',
    render: (p) => (
      <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate" title={p.course}>
        {p.course}
      </td>
    ),
  },
  {
    key: 'student',
    label: 'Студент',
    align: 'right',
    width: 'w-[14%]',
    nullLast: true,
    render: (p) => (
      <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1 truncate" title={p.student || ''}>
        {p.student && p.buyer ? (
          <a
            href={`https://stepik.org/users/${p.buyer}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-cyber-blue hover:underline"
          >
            {p.student}
          </a>
        ) : (
          p.student || '—'
        )}
      </td>
    ),
  },
  {
    key: 'payment_amount',
    label: 'Оплата',
    align: 'right',
    width: 'w-[8%]',
    numeric: true,
    nullLast: true,
    render: (p) => (
      <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300 truncate">
        {formatCurrency(p.payment_amount)}
      </td>
    ),
  },
  {
    key: 'commission',
    label: 'Комиссия',
    align: 'right',
    width: 'w-[8%]',
    numeric: true,
    nullLast: true,
    getValue: (p) => commissionOf(p)?.pct ?? null,
    render: (p) => {
      const c = commissionOf(p);
      return (
        <td
          className="text-right font-mono text-xs pl-1 pr-1 text-gray-300 truncate"
          title={c ? formatCurrency(c.amount) : ''}
        >
          {c ? `${c.pct}%` : '—'}
        </td>
      );
    },
  },
  {
    key: 'amount',
    label: 'Доход',
    align: 'right',
    width: 'w-[8%]',
    numeric: true,
    nullLast: true,
    render: (p) => (
      <td
        className={`text-right font-mono text-xs pl-1 pr-1 truncate ${p.status === 'refunded' ? 'text-crimson-alert line-through' : 'text-neon-green'}`}
      >
        {formatCurrency(p.amount)}
      </td>
    ),
  },
  {
    key: 'channel',
    label: 'Канал',
    align: 'right',
    width: 'w-[6%]',
    nullLast: true,
    render: (p) => <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate">{p.channel || '—'}</td>,
  },
  {
    key: 'promo_code',
    label: 'Промокод',
    align: 'right',
    width: 'w-[12%]',
    nullLast: true,
    render: (p) => <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate">{p.promo_code || '—'}</td>,
  },
  {
    key: 'is_gift',
    label: 'Подарок',
    align: 'right',
    width: 'w-[4%]',
    numeric: true,
    nullLast: true,
    getValue: (p) => (p.is_gift ? 1 : 0),
    render: (p) => <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate">{p.is_gift ? 'Да' : '—'}</td>,
  },
  {
    key: 'utm_source_label',
    label: 'UTM',
    align: 'right',
    width: 'w-[10%]',
    nullLast: true,
    render: (p) => (
      <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate" title={formatUtmTooltip(p.raw)}>
        {p.utm_source_label || '—'}
      </td>
    ),
  },
];

const TAB_COLUMNS = {
  months: MONTHS_COLUMNS,
  years: YEARS_COLUMNS,
  days: DAYS_COLUMNS,
  courses: COURSES_COLUMNS,
  promo: PROMOS_COLUMNS,
  utms: UTMS_COLUMNS,
  recent: RECENT_COLUMNS,
};

const DAYS_TICK = (value) => {
  const [, mm, dd] = String(value).split('-');
  return `${dd}.${mm}`;
};
const MONTHS_PERIOD = (m) => m.month || '';
const DAYS_PERIOD = (d) => {
  const [yyyy, mm, dd] = String(d.day).split('-');
  return `${dd}.${mm}.${yyyy}`;
};

export default function Financials() {
  const { data, error, refresh } = useSync();
  const financials = data.financials;
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const [sorts, setSorts] = useState(SORT_INIT);
  const [viewMode, setViewMode] = useState('table');
  const [chartMetric, setChartMetric] = useState('turnover_income');

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

  const { summary, months, years, courses, promos, utms, recent_payments } = financials || {};
  const dailyRows = useMemo(() => buildDailyStats(recent_payments), [recent_payments]);
  const chartTab = CHARTABLE_TABS.includes(activeTab) ? activeTab : null;
  const chartRows = chartTab === 'months' ? months || [] : dailyRows;
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
                columns={MONTHS_COLUMNS}
                rows={months || []}
                initialSort={SORT_INIT.months}
                sort={sorts.months}
                onSort={onSort('months')}
                rowKey={(m) => `month-${m.year}-${m.month_num}`}
              />
            )}

            {activeTab === 'years' && (
              <DataTable
                columns={YEARS_COLUMNS}
                rows={years || []}
                initialSort={SORT_INIT.years}
                sort={sorts.years}
                onSort={onSort('years')}
                rowKey={(m) => `year-${m.year}`}
              />
            )}

            {activeTab === 'days' && (
              <DataTable
                columns={DAYS_COLUMNS}
                rows={dailyRows}
                initialSort={SORT_INIT.days}
                sort={sorts.days}
                onSort={onSort('days')}
                rowKey={(d) => `day-${d.day}`}
              />
            )}

            {activeTab === 'courses' && (
              <DataTable
                columns={COURSES_COLUMNS}
                rows={courses || []}
                initialSort={SORT_INIT.courses}
                sort={sorts.courses}
                onSort={onSort('courses')}
                rowKey={(c) => `course-${c.course_id}`}
              />
            )}

            {activeTab === 'promo' && (
              <DataTable
                columns={PROMOS_COLUMNS}
                rows={promos || []}
                initialSort={SORT_INIT.promo}
                sort={sorts.promo}
                onSort={onSort('promo')}
                rowKey={(p) => `promo-${p.promo_code}`}
              />
            )}

            {activeTab === 'utms' && (
              <DataTable
                columns={UTMS_COLUMNS}
                rows={utms || []}
                initialSort={SORT_INIT.utms}
                sort={sorts.utms}
                onSort={onSort('utms')}
                rowKey={(u) => `utm-${u.utm_source}`}
              />
            )}

            {activeTab === 'recent' && (
              <DataTable
                columns={RECENT_COLUMNS}
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
