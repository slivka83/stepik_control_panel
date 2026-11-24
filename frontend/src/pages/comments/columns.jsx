import { numCell } from '../../components/NumericCell';
import { STEPIK_URLS } from '../../constants.jsx';
import { fmtDate, yearMonthLabel } from '../../utils/format';
import { monthComposite } from '../../utils/monthWindow';

export const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'courses', label: 'По курсам' },
  { key: 'unanswered', label: 'Не отвеченные' },
  { key: 'disliked', label: 'Дизлайки' },
];

export const SORT_INIT = {
  months: { key: 'month', dir: 'desc' },
  years: { key: 'year', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

export const LIST_SORT_INIT = { key: 'time', dir: 'desc' };

export const LIST_TABS = new Set(['unanswered', 'disliked']);

export const CHART_METRICS = {
  likes_dislikes: {
    label: 'Лайки / Дизлайки',
    format: 'count',
    bars: [
      { dataKey: 'likes', color: '#4ade80' },
      { dataKey: 'dislikes', color: '#f43f5e' },
    ],
    tooltip: (row) => [
      { label: 'Лайки', value: row.likes, color: '#4ade80' },
      { label: 'Дизлайки', value: row.dislikes, color: '#f43f5e' },
      { label: 'Ответы', value: row.replies },
      { label: 'Всего', value: row.total },
    ],
  },
  replies: {
    label: 'Ответы',
    format: 'count',
    bars: [{ dataKey: 'replies', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Ответы', value: row.replies, color: '#38bdf8' }],
  },
  total: {
    label: 'Всего',
    format: 'count',
    bars: [{ dataKey: 'total', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Всего', value: row.total, color: '#38bdf8' }],
  },
};

const num = (row, key) => numCell(row[key] || 0);
const likesCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: '#4ade80' }}>
    {row.likes || 0}
  </td>
);
const dislikesCell = (row) => (
  <td className="text-right font-mono text-xs pl-1 pr-1" style={{ color: '#f43f5e' }}>
    {row.dislikes || 0}
  </td>
);

const commentTextCell = (c) => (
  <td className="text-left pl-1 text-xs truncate">
    <span className="text-gray-300 font-mono text-xs" title={c.text || ''}>
      {c.text || '—'}
    </span>
  </td>
);

const stepCell = (c) => (
  <td className="text-left pl-1 text-xs">
    {c.lesson_id && c.step_number ? (
      <a
        href={STEPIK_URLS.comment(c.lesson_id, c.comment_id)}
        target="_blank"
        rel="noopener noreferrer"
        title={
          c.module_title && c.lesson_title ? `${c.module_title} — ${c.lesson_title}` : `Комментарий ${c.comment_id}`
        }
        className="text-cyber-blue font-mono text-xs hover:underline"
      >
        {c.module_number && c.lesson_number ? `${c.module_number}.${c.lesson_number}-${c.step_number}` : c.step_number}
      </a>
    ) : (
      <span className="text-cyber-blue font-mono text-xs" title={`Комментарий ${c.comment_id}`}>
        {c.comment_id || '—'}
      </span>
    )}
  </td>
);

const studentCell = (c) => (
  <td className="text-left pl-1 text-xs truncate">
    <span className="text-gray-300 font-mono text-xs">{c.user_name || '—'}</span>
  </td>
);

const courseCell = (c) => (
  <td className="text-left pl-1 text-xs truncate">
    {c.stepik_course_id ? (
      <a
        href={STEPIK_URLS.course(c.stepik_course_id)}
        target="_blank"
        rel="noopener noreferrer"
        className="text-cyber-blue font-mono text-xs hover:underline truncate block"
        title={c.course_title}
      >
        {c.course_title}
      </a>
    ) : (
      <span className="text-gray-300 font-mono text-xs">{c.course_title || '—'}</span>
    )}
  </td>
);

const dateCell = (c) => (
  <td className="text-right font-mono text-xs text-gray-400 pl-1 pr-1 whitespace-nowrap">
    {c.time ? fmtDate(c.time) : '—'}
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
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[14%]', numeric: true, render: (m) => num(m, 'total') },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[16%]', numeric: true, render: (m) => likesCell(m) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => dislikesCell(m),
  },
  {
    key: 'replies',
    label: 'Ответы',
    align: 'right',
    width: 'w-[18%]',
    numeric: true,
    render: (m) => num(m, 'replies'),
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
    width: 'w-[16%]',
    numeric: true,
    render: (m) => num(m, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[16%]', numeric: true, render: (m) => num(m, 'total') },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[15%]', numeric: true, render: (m) => likesCell(m) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[15%]',
    numeric: true,
    render: (m) => dislikesCell(m),
  },
  {
    key: 'replies',
    label: 'Ответы',
    align: 'right',
    width: 'w-[16%]',
    numeric: true,
    render: (m) => num(m, 'replies'),
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
    width: 'w-[14%]',
    numeric: true,
    render: (c) => num(c, 'students'),
  },
  { key: 'total', label: 'Всего', align: 'right', width: 'w-[14%]', numeric: true, render: (c) => num(c, 'total') },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[14%]', numeric: true, render: (c) => likesCell(c) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (c) => dislikesCell(c),
  },
  {
    key: 'replies',
    label: 'Ответы',
    align: 'right',
    width: 'w-[14%]',
    numeric: true,
    render: (c) => num(c, 'replies'),
  },
];

export const COMMENTS_LIST_COLUMNS = [
  {
    key: 'time',
    label: 'Дата',
    width: 'w-[12%]',
    nullLast: true,
    naturalDir: 'asc',
    render: dateCell,
  },
  {
    key: 'student',
    label: 'Студент',
    width: 'w-[16%]',
    getValue: (c) => c.user_name || '',
    render: studentCell,
  },
  {
    key: 'course',
    label: 'Курс',
    width: 'w-[16%]',
    getValue: (c) => c.course_title || '',
    render: courseCell,
  },
  {
    key: 'text',
    label: 'Комментарий',
    width: 'w-[26%]',
    getValue: (c) => c.text || '',
    render: commentTextCell,
  },
  { key: 'likes', label: 'Лайки', align: 'right', width: 'w-[7%]', numeric: true, render: (c) => likesCell(c) },
  {
    key: 'dislikes',
    label: 'Дизлайки',
    align: 'right',
    width: 'w-[7%]',
    numeric: true,
    render: (c) => dislikesCell(c),
  },
  { key: 'replies', label: 'Ответы', align: 'right', width: 'w-[7%]', numeric: true, render: (c) => num(c, 'replies') },
  {
    key: 'step',
    label: 'Шаг',
    width: 'w-[9%]',
    numeric: true,
    getValue: (c) => c.step_number,
    render: stepCell,
  },
];

export const TAB_COLUMNS = {
  months: MONTH_COLUMNS,
  years: YEARS_COLUMNS,
  courses: COURSES_COLUMNS,
};
