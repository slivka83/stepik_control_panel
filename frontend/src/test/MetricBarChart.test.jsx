import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MetricBarChart from '../components/MetricBarChart';

const rows = [
  { month: 'Январь 2026', year: 2026, total: 10, likes: 8, dislikes: 2, turnover: 70000, income: 50000 },
  { month: 'Февраль 2026', year: 2026, total: 20, likes: 15, dislikes: 5, turnover: 90000, income: 60000 },
];

const metrics = {
  stacked: {
    label: 'Лайки / Дизлайки',
    format: 'count',
    bars: [
      { dataKey: 'likes', color: '#4ade80' },
      { dataKey: 'dislikes', color: '#f43f5e' },
    ],
    tooltip: (row) => [
      { label: 'Лайки', value: row.likes, color: '#4ade80' },
      { label: 'Дизлайки', value: row.dislikes, color: '#f43f5e' },
      { label: 'Всего', value: row.total },
    ],
  },
  money: {
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
  single: {
    label: 'Всего',
    format: 'count',
    bars: [{ dataKey: 'total', color: '#38bdf8' }],
    tooltip: (row) => [{ label: 'Всего', value: row.total, color: '#38bdf8' }],
  },
};

const baseProps = {
  rows,
  metric: 'stacked',
  metrics,
  xTick: (value) => value.substring(0, 3),
  periodLabel: (m) => m.month,
};

describe('MetricBarChart', () => {
  it('renders empty state when no rows', () => {
    render(<MetricBarChart {...baseProps} rows={[]} />);
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument();
  });

  it('renders figcaption with metric label and period count', () => {
    const { container } = render(<MetricBarChart {...baseProps} />);
    const figcaption = container.querySelector('figcaption');
    expect(figcaption.textContent).toContain('Лайки / Дизлайки');
    expect(figcaption.textContent).toContain('2');
  });

  it('renders figure with accessible name per metric', () => {
    render(<MetricBarChart {...baseProps} />);
    expect(screen.getByRole('img', { name: 'Диаграмма Лайки / Дизлайки' })).toBeInTheDocument();
    render(<MetricBarChart {...baseProps} metric="money" />);
    expect(screen.getByRole('img', { name: 'Диаграмма Оборот / Доход' })).toBeInTheDocument();
    render(<MetricBarChart {...baseProps} metric="single" />);
    expect(screen.getByRole('img', { name: 'Диаграмма Всего' })).toBeInTheDocument();
  });

  it('handles a custom xKey', () => {
    const dayRows = [
      { day: '2026-01-15', total: 3, likes: 2, dislikes: 1 },
      { day: '2026-01-14', total: 1, likes: 1, dislikes: 0 },
    ];
    render(
      <MetricBarChart
        rows={dayRows}
        xKey="day"
        metric="single"
        metrics={metrics}
        xTick={(value) => value.slice(5).replace('-', '.')}
        periodLabel={(d) => d.day}
      />,
    );
    expect(screen.getByRole('img', { name: 'Диаграмма Всего' })).toBeInTheDocument();
  });
});
