import { numCell } from '../../components/NumericCell';
import { STEPIK_URLS } from '../../constants.jsx';
import { formatRating, getRatingColor, yearMonthLabel } from '../../utils/format';
import { monthComposite } from '../../utils/monthWindow';

export const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
];

export const CHART_METRICS = {
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

export const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

const num = (row, key) => numCell(row[key] || 0);
const scoreCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1">
    {row.avg_score ? (
      <span className="font-bold" style={{ color: getRatingColor(row.avg_score) }}>
        {formatRating(row.avg_score)}
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

export const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
};
