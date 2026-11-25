import { numCell } from '../../components/NumericCell';
import { STEPIK_URLS } from '../../constants.jsx';
import { fmtDate, formatRating, getRatingColor } from '../../utils/format';

const numCellLocal = (row, key) => numCell(row[key] || 0);

export const COURSE_COLUMNS = [
  {
    key: 'title',
    label: 'Название',
    width: 'w-[25%]',
    render: (c) => (
      <td className="pl-1 pr-1 truncate">
        <a
          href={STEPIK_URLS.course(c.stepik_course_id)}
          target="_blank"
          rel="noopener noreferrer"
          className="text-cyber-blue font-mono text-xs hover:underline truncate block"
          title={c.title}
        >
          {c.title}
        </a>
      </td>
    ),
  },
  {
    key: 'status',
    label: 'Статус',
    align: 'right',
    width: 'w-[9%]',
    // Sort by the visible Russian label, not the backend's English value.
    getValue: (c) => (c.status?.toLowerCase() === 'published' ? 'Опубликован' : 'Черновик'),
    render: (c) => {
      const isPublished = c.status?.toLowerCase() === 'published';
      return (
        <td className="pr-1 text-right">
          <span
            className={`inline-block px-2 rounded text-xs font-medium ${
              isPublished ? 'bg-neon-green/20 text-neon-green' : 'bg-gray-500/20 text-gray-400'
            }`}
          >
            {isPublished ? 'Опубликован' : 'Черновик'}
          </span>
        </td>
      );
    },
  },
  {
    key: 'enrollment_count',
    label: 'Студенты',
    align: 'right',
    width: 'w-[7%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'enrollment_count'),
  },
  {
    key: 'certificates_count',
    label: 'Сертификаты',
    align: 'right',
    width: 'w-[10%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'certificates_count'),
  },
  {
    key: 'comments_count',
    label: 'Комментарии',
    align: 'right',
    width: 'w-[9%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'comments_count'),
  },
  {
    key: 'reviews_count',
    label: 'Отзывы',
    align: 'right',
    width: 'w-[6%]',
    numeric: true,
    render: (c) => numCellLocal(c, 'reviews_count'),
  },
  {
    key: 'average_rating',
    label: 'Рейтинг',
    align: 'right',
    width: 'w-[7%]',
    numeric: true,
    render: (c) =>
      c.average_rating ? (
        <td className="text-right pr-1">
          <span className="font-mono font-bold" style={{ color: getRatingColor(c.average_rating) }}>
            {formatRating(c.average_rating)}
          </span>
        </td>
      ) : (
        <td className="text-right pr-1">
          <span className="text-gray-500">—</span>
        </td>
      ),
  },
  {
    key: 'price',
    label: 'Стоимость',
    align: 'right',
    width: 'w-[8%]',
    numeric: true,
    nullLast: true,
    render: (c) => (
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1">
        {c.price != null ? `${c.price.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
    ),
  },
  {
    key: 'income',
    label: 'Доход',
    align: 'right',
    width: 'w-[10%]',
    numeric: true,
    nullLast: true,
    render: (c) => (
      <td className="text-right font-mono text-xs pl-1 pr-1 text-neon-green">
        {c.income != null ? `${c.income.toLocaleString('ru-RU')}\u00A0₽` : '—'}
      </td>
    ),
  },
  {
    key: 'published_at',
    label: 'Опубликован',
    align: 'right',
    width: 'w-[9%]',
    nullLast: true,
    naturalDir: 'desc',
    render: (c) => (
      <td className="text-right font-mono text-xs text-gray-300 pl-1 pr-1 truncate">{fmtDate(c.published_at)}</td>
    ),
  },
];
