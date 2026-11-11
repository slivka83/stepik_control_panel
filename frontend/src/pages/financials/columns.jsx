import { formatCurrency } from '../../utils/formatNumber';
import { yearMonthLabel } from '../../utils/format';
import { formatUtmTooltip, paymentCommission } from '../../utils/financials';

export const TABS = [
  { key: 'months', label: 'По месяцам' },
  { key: 'years', label: 'По годам' },
  { key: 'days', label: 'По дням' },
  { key: 'courses', label: 'По курсам' },
  { key: 'promo', label: 'По промокодам' },
  { key: 'utms', label: 'По UTM' },
  { key: 'recent', label: 'Последние операции' },
];

export const CHARTABLE_TABS = ['months', 'days'];

export const CHART_METRICS = {
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

export const SORT_INIT = {
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
    getValue: (p) => paymentCommission(p)?.pct ?? null,
    render: (p) => {
      const c = paymentCommission(p);
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

export const TAB_COLUMNS = {
  months: MONTHS_COLUMNS,
  years: YEARS_COLUMNS,
  days: DAYS_COLUMNS,
  courses: COURSES_COLUMNS,
  promo: PROMOS_COLUMNS,
  utms: UTMS_COLUMNS,
  recent: RECENT_COLUMNS,
};

export const DAYS_TICK = (value) => {
  const [, mm, dd] = String(value).split('-');
  return `${dd}.${mm}`;
};

export const MONTHS_PERIOD = (m) => m.month || '';

export const DAYS_PERIOD = (d) => {
  const [yyyy, mm, dd] = String(d.day).split('-');
  return `${dd}.${mm}.${yyyy}`;
};
