import { numCell } from '../../components/NumericCell';
import { STEPIK_URLS } from '../../constants.jsx';
import { yearMonthLabel } from '../../utils/format';
import { monthComposite } from '../../utils/monthWindow';

export const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
];

export const CHART_METRICS = {
  type_split: {
    label: 'С отличием / Обычные',
    format: 'count',
    bars: [
      { dataKey: 'distinction', color: '#DB62C4' },
      { dataKey: 'regular', color: '#B70094' },
    ],
    tooltip: (row) => [
      { label: 'С отличием', value: row.distinction, color: '#DB62C4' },
      { label: 'Обычные', value: row.regular, color: '#B70094' },
      { label: 'Всего', value: row.total },
    ],
  },
  total: {
    label: 'Всего',
    format: 'count',
    bars: [{ dataKey: 'total', color: '#DB62C4' }],
    tooltip: (row) => [{ label: 'Всего', value: row.total, color: '#DB62C4' }],
  },
  students: {
    label: 'Студенты',
    format: 'count',
    bars: [{ dataKey: 'students', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Студенты', value: row.students, color: '#38bdf8' }],
  },
};

export const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

const DISTINCTION_COLOR = '#DB62C4';
const REGULAR_COLOR = '#B70094';

const num = (row, key) => numCell(row[key] || 0);
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
    key: 'distinction',
    label: 'С отличием',
    align: 'right',
    width: 'w-[21%]',
    numeric: true,
    render: (m) => distinctionCell(m),
  },
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
    key: 'distinction',
    label: 'С отличием',
    align: 'right',
    width: 'w-[21%]',
    numeric: true,
    render: (m) => distinctionCell(m),
  },
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
    key: 'distinction',
    label: 'С отличием',
    align: 'right',
    width: 'w-[18%]',
    numeric: true,
    render: (c) => distinctionCell(c),
  },
  { key: 'regular', label: 'Обычные', align: 'right', width: 'w-[18%]', numeric: true, render: (c) => regularCell(c) },
];

export const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
};
