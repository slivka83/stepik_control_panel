import { memo, useState, useEffect, useRef, useLayoutEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import { formatCurrency } from '../utils/formatNumber';
import ErrorBanner from '../components/ErrorBanner';
import KpiCard from '../components/KpiCard';

const ROW_HEIGHT = 35;
const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'promo', label: 'По промокодам' },
  { key: 'utms', label: 'По UTM' },
  { key: 'recent', label: 'Последние операции' },
];

function yearMonthLabel(label) {
  const parts = String(label).split(' ');
  if (parts.length === 2 && /^\d{4}$/.test(parts[1])) return `${parts[1]} ${parts[0]}`;
  return label;
}

function calcRowsPerPage(node) {
  const header = node.querySelector('thead');
  const headerH = header?.offsetHeight || 0;
  const row = node.querySelector('tbody tr');
  const rowH = row?.offsetHeight || ROW_HEIGHT;
  const avail = node.clientHeight - headerH - 4;
  return Math.max(1, Math.floor(avail / rowH));
}

const NATURAL_DIR_BY_KEY = {
  month: 'asc',
  year: 'asc',
  payments_count: 'asc',
  turnover: 'asc',
  income: 'asc',
  refunds: 'asc',
  title: 'desc',
  payments: 'asc',
  price: 'asc',
  promo_code: 'desc',
  last_used: 'asc',
  utm_source: 'desc',
  time: 'asc',
  course: 'desc',
  student: 'desc',
  payment_amount: 'asc',
  amount: 'asc',
  channel: 'desc',
  is_gift: 'asc',
  utm_source_label: 'desc',
};

const MONTHS_SORT_COLUMNS = {
  month: { numeric: true },
  payments_count: { numeric: true },
  turnover: { numeric: true },
  income: { numeric: true },
  refunds: { numeric: true },
};

const YEARS_SORT_COLUMNS = {
  year: { numeric: true },
  payments_count: { numeric: true },
  turnover: { numeric: true },
  income: { numeric: true },
  refunds: { numeric: true },
};

const COURSES_SORT_COLUMNS = {
  title: { numeric: false },
  payments: { numeric: true },
  turnover: { numeric: true },
  income: { numeric: true },
  price: { numeric: true, nullLast: true },
  refunds: { numeric: true },
};

const PROMOS_SORT_COLUMNS = {
  promo_code: { numeric: false },
  payments: { numeric: true },
  turnover: { numeric: true },
  income: { numeric: true },
  refunds: { numeric: true },
  last_used: { numeric: false, nullLast: true },
};

const UTMS_SORT_COLUMNS = {
  utm_source: { numeric: false },
  payments: { numeric: true },
  turnover: { numeric: true },
  income: { numeric: true },
  refunds: { numeric: true },
  last_used: { numeric: false, nullLast: true },
};

const RECENT_SORT_COLUMNS = {
  time: { numeric: false },
  course: { numeric: false },
  student: { numeric: false, nullLast: true },
  payment_amount: { numeric: true },
  amount: { numeric: true },
  channel: { numeric: false, nullLast: true },
  promo_code: { numeric: false, nullLast: true },
  is_gift: { numeric: true, nullLast: true },
  utm_source_label: { numeric: false, nullLast: true },
};

const TAB_SORT_COLUMNS = {
  months: MONTHS_SORT_COLUMNS,
  years: YEARS_SORT_COLUMNS,
  courses: COURSES_SORT_COLUMNS,
  promo: PROMOS_SORT_COLUMNS,
  utms: UTMS_SORT_COLUMNS,
  recent: RECENT_SORT_COLUMNS,
};

const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'income', dir: 'desc' },
  promo: { key: 'income', dir: 'desc' },
  utms: { key: 'income', dir: 'desc' },
  recent: { key: 'time', dir: 'desc' },
};

function getSortValue(item, key) {
  if (key === 'month') {
    const ym = item.year != null && item.month_num != null ? item.year * 100 + item.month_num : NaN;
    if (Number.isFinite(ym)) return ym;
  }
  if (key === 'is_gift') return item.is_gift ? 1 : 0;
  return item[key];
}

const makeComparator = (columns) => (a, b, key, dir) => {
  const cfg = columns[key];
  const va = getSortValue(a, key);
  const vb = getSortValue(b, key);
  if (cfg.nullLast) {
    if (va == null && vb == null) return 0;
    if (va == null) return 1;
    if (vb == null) return -1;
  }
  let diff;
  if (cfg.numeric) {
    diff = (va ?? 0) - (vb ?? 0);
  } else {
    diff = String(va ?? '')
      .toLowerCase()
      .localeCompare(String(vb ?? '').toLowerCase(), 'ru');
  }
  return dir === 'asc' ? diff : -diff;
};

const compareMonths = makeComparator(MONTHS_SORT_COLUMNS);
const compareYears = makeComparator(YEARS_SORT_COLUMNS);
const compareCourses = makeComparator(COURSES_SORT_COLUMNS);
const comparePromos = makeComparator(PROMOS_SORT_COLUMNS);
const compareUtms = makeComparator(UTMS_SORT_COLUMNS);
const compareRecent = makeComparator(RECENT_SORT_COLUMNS);

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

function formatUtmTooltip(raw) {
  const utm = raw?.last_course_click_utm;
  if (!utm || typeof utm !== 'object') return '';
  return Object.entries(utm)
    .map(([k, v]) => `${k}: ${v ?? ''}`)
    .join('\n');
}

export default function Financials() {
  const { data, error, refresh } = useSync();
  const financials = data.financials;
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const [page, setPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [sorts, setSorts] = useState(SORT_INIT);
  const tableRef = useRef(null);
  const prevRows = useRef(0);
  const resizeRef = useRef(null);

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
    setPage(1);
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
  }, [activeTab]);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    setSearchParams({ tab });
  };

  const onSort = (tab) => (key) => {
    setSorts((prev) => {
      const cur = prev[tab];
      const cfg = TAB_SORT_COLUMNS[tab][key];
      const next =
        cur.key === key
          ? { key, dir: cur.dir === 'asc' ? 'desc' : 'asc' }
          : { key, dir: cfg.numeric ? 'desc' : 'asc' };
      return { ...prev, [tab]: next };
    });
  };

  const { summary, months, years, courses, promos, utms, recent_payments } = financials || {};

  const sortedMonths = [...(months || [])].sort((a, b) => compareMonths(a, b, sorts.months.key, sorts.months.dir));
  const monthsTotalPages = Math.max(1, Math.ceil(sortedMonths.length / rowsPerPage));
  const monthsPage = Math.min(page, monthsTotalPages);
  const paginatedMonths = sortedMonths.slice((monthsPage - 1) * rowsPerPage, monthsPage * rowsPerPage);

  const sortedYears = [...(years || [])].sort((a, b) => compareYears(a, b, sorts.years.key, sorts.years.dir));
  const yearsTotalPages = Math.max(1, Math.ceil(sortedYears.length / rowsPerPage));
  const yearsPage = Math.min(page, yearsTotalPages);
  const paginatedYears = sortedYears.slice((yearsPage - 1) * rowsPerPage, yearsPage * rowsPerPage);

  const sortedCourses = [...(courses || [])].sort((a, b) => compareCourses(a, b, sorts.courses.key, sorts.courses.dir));
  const coursesTotalPages = Math.max(1, Math.ceil(sortedCourses.length / rowsPerPage));
  const coursesPage = Math.min(page, coursesTotalPages);
  const paginatedCourses = sortedCourses.slice((coursesPage - 1) * rowsPerPage, coursesPage * rowsPerPage);

  const sortedPromos = [...(promos || [])].sort((a, b) => comparePromos(a, b, sorts.promo.key, sorts.promo.dir));
  const promosTotalPages = Math.max(1, Math.ceil(sortedPromos.length / rowsPerPage));
  const promosPage = Math.min(page, promosTotalPages);
  const paginatedPromos = sortedPromos.slice((promosPage - 1) * rowsPerPage, promosPage * rowsPerPage);

  const sortedUtms = [...(utms || [])].sort((a, b) => compareUtms(a, b, sorts.utms.key, sorts.utms.dir));
  const utmsTotalPages = Math.max(1, Math.ceil(sortedUtms.length / rowsPerPage));
  const utmsPage = Math.min(page, utmsTotalPages);
  const paginatedUtms = sortedUtms.slice((utmsPage - 1) * rowsPerPage, utmsPage * rowsPerPage);

  const sortedPayments = [...(recent_payments || [])].sort((a, b) => compareRecent(a, b, sorts.recent.key, sorts.recent.dir));
  const paymentsTotalPages = Math.max(1, Math.ceil(sortedPayments.length / rowsPerPage));
  const paymentsPage = Math.min(page, paymentsTotalPages);
  const paginatedPayments = sortedPayments.slice((paymentsPage - 1) * rowsPerPage, paymentsPage * rowsPerPage);

  useEffect(() => {
    const totals = {
      months: monthsTotalPages,
      years: yearsTotalPages,
      courses: coursesTotalPages,
      promo: promosTotalPages,
      utms: utmsTotalPages,
      recent: paymentsTotalPages,
    };
    if (page > totals[activeTab]) setPage(totals[activeTab]);
  }, [page, activeTab, monthsTotalPages, yearsTotalPages, coursesTotalPages, promosTotalPages, utmsTotalPages, paymentsTotalPages]);

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 shrink-0">
        <KpiCard title="Оборот" value={summary?.total_turnover || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Доход" value={summary?.total_income || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Возвраты" value={summary?.total_refunds || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Чистый доход" value={summary?.net_income || 0} color="white" suffix={'\u200A₽'} />
        <KpiCard title="Покупок" value={summary?.total_payments || 0} color="white" />
      </div>

      <div className="flex flex-col flex-1 min-h-0">
      <div className="inline-flex self-start gap-2 pb-0 shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => handleTabChange(tab.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.key
                ? 'border-cyber-blue text-cyber-blue'
                : 'border-transparent text-gray-400 hover:text-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'months' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Месяц" sortKey="month" sort={sorts.months} onSort={onSort('months')} width="w-[28%]" />
                  <SortableTh label="Покупок" sortKey="payments_count" sort={sorts.months} onSort={onSort('months')} align="right" width="w-[16%]" />
                  <SortableTh label="Оборот" sortKey="turnover" sort={sorts.months} onSort={onSort('months')} align="right" width="w-[22%]" />
                  <SortableTh label="Доход" sortKey="income" sort={sorts.months} onSort={onSort('months')} align="right" width="w-[20%]" />
                  <SortableTh label="Возвраты" sortKey="refunds" sort={sorts.months} onSort={onSort('months')} align="right" width="w-[14%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedMonths.map((m) => (
                  <tr key={`month-${m.year}-${m.month_num}`} className="border-b border-gray-800">
                    <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{yearMonthLabel(m.month)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{m.payments_count}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{formatCurrency(m.turnover)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">{formatCurrency(m.income)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-crimson-alert">
                      {m.refunds > 0 ? `-${formatCurrency(m.refunds)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={monthsPage} totalPages={monthsTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'years' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Год" sortKey="year" sort={sorts.years} onSort={onSort('years')} width="w-[28%]" />
                  <SortableTh label="Покупок" sortKey="payments_count" sort={sorts.years} onSort={onSort('years')} align="right" width="w-[16%]" />
                  <SortableTh label="Оборот" sortKey="turnover" sort={sorts.years} onSort={onSort('years')} align="right" width="w-[22%]" />
                  <SortableTh label="Доход" sortKey="income" sort={sorts.years} onSort={onSort('years')} align="right" width="w-[20%]" />
                  <SortableTh label="Возвраты" sortKey="refunds" sort={sorts.years} onSort={onSort('years')} align="right" width="w-[14%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedYears.map((m) => (
                  <tr key={`year-${m.year}`} className="border-b border-gray-800">
                    <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{m.year}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{m.payments_count}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{formatCurrency(m.turnover)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">{formatCurrency(m.income)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-crimson-alert">
                      {m.refunds > 0 ? `-${formatCurrency(m.refunds)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={yearsPage} totalPages={yearsTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'courses' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Курс" sortKey="title" sort={sorts.courses} onSort={onSort('courses')} width="w-[32%]" />
                  <SortableTh label="Покупок" sortKey="payments" sort={sorts.courses} onSort={onSort('courses')} align="right" width="w-[12%]" />
                  <SortableTh label="Оборот" sortKey="turnover" sort={sorts.courses} onSort={onSort('courses')} align="right" width="w-[14%]" />
                  <SortableTh label="Доход" sortKey="income" sort={sorts.courses} onSort={onSort('courses')} align="right" width="w-[14%]" />
                  <SortableTh label="Возвраты" sortKey="refunds" sort={sorts.courses} onSort={onSort('courses')} align="right" width="w-[14%]" />
                  <SortableTh label="Стоимость" sortKey="price" sort={sorts.courses} onSort={onSort('courses')} align="right" width="w-[14%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedCourses.map((c) => (
                  <tr key={`course-${c.course_id}`} className="border-b border-gray-800">
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
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{c.payments}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{formatCurrency(c.turnover)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">{formatCurrency(c.income)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-crimson-alert">
                      {c.refunds > 0 ? `-${formatCurrency(c.refunds)}` : '—'}
                    </td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{c.price ? formatCurrency(c.price) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={coursesPage} totalPages={coursesTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'promo' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Промокод" sortKey="promo_code" sort={sorts.promo} onSort={onSort('promo')} width="w-[18%]" />
                  <SortableTh label="Покупок" sortKey="payments" sort={sorts.promo} onSort={onSort('promo')} align="right" width="w-[12%]" />
                  <SortableTh label="Оборот" sortKey="turnover" sort={sorts.promo} onSort={onSort('promo')} align="right" width="w-[18%]" />
                  <SortableTh label="Доход" sortKey="income" sort={sorts.promo} onSort={onSort('promo')} align="right" width="w-[16%]" />
                  <SortableTh label="Возвраты" sortKey="refunds" sort={sorts.promo} onSort={onSort('promo')} align="right" width="w-[14%]" />
                  <SortableTh label="Последнее применение" sortKey="last_used" sort={sorts.promo} onSort={onSort('promo')} align="right" width="w-[22%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedPromos.map((p) => (
                  <tr key={`promo-${p.promo_code}`} className="border-b border-gray-800">
                    <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{p.promo_code}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{p.payments}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{formatCurrency(p.turnover)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">{formatCurrency(p.income)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-crimson-alert">
                      {p.refunds > 0 ? `-${formatCurrency(p.refunds)}` : '—'}
                    </td>
                    <td className="text-right text-gray-400 text-xs pl-1 pr-1 truncate">
                      {p.last_used ? new Date(p.last_used).toLocaleDateString('ru-RU') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={promosPage} totalPages={promosTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'utms' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="UTM" sortKey="utm_source" sort={sorts.utms} onSort={onSort('utms')} width="w-[18%]" />
                  <SortableTh label="Покупок" sortKey="payments" sort={sorts.utms} onSort={onSort('utms')} align="right" width="w-[12%]" />
                  <SortableTh label="Оборот" sortKey="turnover" sort={sorts.utms} onSort={onSort('utms')} align="right" width="w-[18%]" />
                  <SortableTh label="Доход" sortKey="income" sort={sorts.utms} onSort={onSort('utms')} align="right" width="w-[16%]" />
                  <SortableTh label="Возвраты" sortKey="refunds" sort={sorts.utms} onSort={onSort('utms')} align="right" width="w-[14%]" />
                  <SortableTh label="Последнее применение" sortKey="last_used" sort={sorts.utms} onSort={onSort('utms')} align="right" width="w-[22%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedUtms.map((u) => (
                  <tr key={`utm-${u.utm_source}`} className="border-b border-gray-800">
                    <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">{u.utm_source}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{u.payments}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300">{formatCurrency(u.turnover)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">{formatCurrency(u.income)}</td>
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-crimson-alert">
                      {u.refunds > 0 ? `-${formatCurrency(u.refunds)}` : '—'}
                    </td>
                    <td className="text-right text-gray-400 text-xs pl-1 pr-1 truncate">
                      {u.last_used ? new Date(u.last_used).toLocaleDateString('ru-RU') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={utmsPage} totalPages={utmsTotalPages} setPage={setPage} />
        </div>
      )}

      {activeTab === 'recent' && (
        <div className="glass-panel p-4 flex flex-col flex-1 min-h-0 rounded-tl-none">
          <div ref={tableRef} className="overflow-hidden flex-1 min-h-0">
            <table className="w-full text-sm table-fixed fin-table sol-table">
              <thead>
                <tr className="border-b border-gray-700">
                  <SortableTh label="Дата" sortKey="time" sort={sorts.recent} onSort={onSort('recent')} width="w-[12%]" />
                  <SortableTh label="Курс" sortKey="course" sort={sorts.recent} onSort={onSort('recent')} width="w-[26%]" />
                  <SortableTh label="Студент" sortKey="student" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[14%]" />
                  <SortableTh label="Оплата" sortKey="payment_amount" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[8%]" />
                  <SortableTh label="Доход" sortKey="amount" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[8%]" />
                  <SortableTh label="Канал" sortKey="channel" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[6%]" />
                  <SortableTh label="Промокод" sortKey="promo_code" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[12%]" />
                  <SortableTh label="Подарок" sortKey="is_gift" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[4%]" />
                  <SortableTh label="UTM" sortKey="utm_source_label" sort={sorts.recent} onSort={onSort('recent')} align="right" width="w-[10%]" />
                </tr>
              </thead>
              <tbody>
                {paginatedPayments.map((p) => (
                  <tr key={`payment-${p.id}`} className="border-b border-gray-800">
                    <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate">
                      {`${new Date(p.time).toLocaleDateString('ru-RU')} ${new Date(p.time).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`}
                    </td>
                    <td className="text-gray-300 font-mono text-xs pl-1 pr-1 truncate" title={p.course}>
                      {p.course}
                    </td>
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
                    <td className="text-right font-mono text-xs pl-1 pr-1 text-gray-300 truncate">
                      {formatCurrency(p.payment_amount)}
                    </td>
                    <td
                      className={`text-right font-mono text-xs pl-1 pr-1 truncate ${p.status === 'refunded' ? 'text-crimson-alert line-through' : 'text-neon-green'}`}
                    >
                      {formatCurrency(p.amount)}
                    </td>
                    <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate">{p.channel || '—'}</td>
                    <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate">{p.promo_code || '—'}</td>
                    <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate">{p.is_gift ? 'Да' : '—'}</td>
                    <td className="text-right text-gray-300 text-xs pl-1 pr-1 truncate" title={formatUtmTooltip(p.raw)}>
                      {p.utm_source_label || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination page={paymentsPage} totalPages={paymentsTotalPages} setPage={setPage} />
        </div>
      )}
      </div>
    </div>
  );
}
