import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import ErrorBanner from '../components/ErrorBanner';
import DataTable from '../components/DataTable';
import Tabs from '../components/Tabs';
import { parseMonthLabel } from '../utils/monthWindow';
import { yearMonthLabel } from '../utils/format';
import { STEPIK_URLS } from '../constants.jsx';

const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
];

const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

const DISTINCTION_COLOR = '#DB62C4';
const REGULAR_COLOR = '#B70094';

function monthComposite(m) {
  const p = parseMonthLabel(m.month);
  return p ? p.year * 100 + p.month : 0;
}

const num = (row, key) => (
  <td className="text-right text-gray-300 font-mono text-xs pl-1 pr-1">{row[key] || 0}</td>
);
const distinctionCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: DISTINCTION_COLOR }}>
    {row.distinction || 0}
  </td>
);
const regularCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: REGULAR_COLOR }}>
    {row.regular || 0}
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
  { key: 'students', label: 'Студенты', align: 'right', width: 'w-[18%]', numeric: true, render: (m) => num(m, 'students') },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[18%]', numeric: true, render: (m) => num(m, 'total') },
  { key: 'distinction', label: 'С отличием', align: 'right', width: 'w-[21%]', numeric: true, render: (m) => distinctionCell(m) },
  { key: 'regular', label: 'Обычные', align: 'right', width: 'w-[21%]', numeric: true, render: (m) => regularCell(m) },
];

const YEARS_COLUMNS = [
  {
    key: 'year',
    label: 'Год',
    width: 'w-[22%]',
    numeric: true,
    render: (m) => <td className="text-gray-300 font-mono text-xs pl-1 truncate">{m.year}</td>,
  },
  { key: 'students', label: 'Студенты', align: 'right', width: 'w-[18%]', numeric: true, render: (m) => num(m, 'students') },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[18%]', numeric: true, render: (m) => num(m, 'total') },
  { key: 'distinction', label: 'С отличием', align: 'right', width: 'w-[21%]', numeric: true, render: (m) => distinctionCell(m) },
  { key: 'regular', label: 'Обычные', align: 'right', width: 'w-[21%]', numeric: true, render: (m) => regularCell(m) },
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
            href={STEPIK_URLS.certificates(c.stepik_course_id)}
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
  { key: 'students', label: 'Студенты', align: 'right', width: 'w-[17%]', numeric: true, render: (c) => num(c, 'students') },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[17%]', numeric: true, render: (c) => num(c, 'total') },
  { key: 'distinction', label: 'С отличием', align: 'right', width: 'w-[18%]', numeric: true, render: (c) => distinctionCell(c) },
  { key: 'regular', label: 'Обычные', align: 'right', width: 'w-[18%]', numeric: true, render: (c) => regularCell(c) },
];

const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
};

export default function Certificates() {
  const { data, error, refresh } = useSync();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') || 'months');
  const [sorts, setSorts] = useState(SORT_INIT);

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

  const stats = data.certificatesStats || {};
  const months = stats.months || [];
  const years = stats.years || [];
  const byCourse = stats.by_course || [];
  const totals = stats.totals || {};

  return (
    <div className="flex flex-col flex-1 h-0 gap-4">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 shrink-0">
        <KpiCard title="Всего сертификатов" value={totals.certificates || 0} color="white" />
        <KpiCard title="Студенты" value={totals.students || 0} color="white" />
        <KpiCard title="С отличием" value={totals.distinction || 0} color="distinction" />
        <KpiCard title="Обычные" value={totals.regular || 0} color="regular" />
      </div>

      <div className="flex flex-col flex-1 min-h-0">
        <Tabs items={TABS} active={activeTab} onChange={handleTabChange} />

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
      </div>
    </div>
  );
}
