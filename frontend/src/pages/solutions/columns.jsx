import { numCell } from '../../components/NumericCell';
import { STEPIK_URLS } from '../../constants.jsx';
import { yearMonthLabel } from '../../utils/format';
import { monthComposite } from '../../utils/monthWindow';

export const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'hardest', label: 'Самые сложные' },
];

export const CHART_METRICS = {
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

export const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
  hardest: { key: 'weighted_success', dir: 'asc' },
};

export function successColor(pct) {
  if (pct < 33) return '#f43f5e';
  if (pct < 66) return '#f59e0b';
  return '#4ade80';
}

export function calcWrong(m) {
  return (m.total || 0) - (m.correct || 0);
}

export function calcPct(m) {
  return m.total > 0 ? ((m.correct || 0) / m.total) * 100 : 0;
}

const num = (row, key) => numCell((row[key] || 0).toLocaleString('ru-RU'));

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
    getValue: (s) => calcPct(s),
    render: (s) => successCell(calcPct(s)),
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

export const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
  hardest: HARDEST_COLUMNS,
};
