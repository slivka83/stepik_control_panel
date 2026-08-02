import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ActiveStudentsChart from '../components/ActiveStudentsChart';
import { formatMonthLabel } from '../utils/monthWindow';

describe('ActiveStudentsChart', () => {
  it('renders empty state when no months data', () => {
    render(<ActiveStudentsChart data={{}} />);
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument();
  });

  it('renders chart title', () => {
    render(<ActiveStudentsChart data={{ months: [] }} />);
    expect(screen.getByText('Активные студенты')).toBeInTheDocument();
  });

  it('renders with data', () => {
    const data = {
      months: [
        { month: 'Январь 2026', light: 100, dark: 80 },
        { month: 'Февраль 2026', light: 150, dark: 120 },
      ],
    };
    render(<ActiveStudentsChart data={data} />);
    expect(screen.getByText('Активные студенты')).toBeInTheDocument();
    expect(screen.queryByText('Нет данных для отображения')).not.toBeInTheDocument();
  });

  it('renders legend items', () => {
    const data = { months: [{ month: 'Январь 2026', light: 100, dark: 80 }] };
    render(<ActiveStudentsChart data={data} />);
    expect(screen.getByText('Уникальные')).toBeInTheDocument();
    expect(screen.getByText('Уникальные по курсам')).toBeInTheDocument();
  });

  it('shows 18 months ending with the current month even with sparse data', () => {
    // Regression: окно обязано быть привязано к текущему месяцу (18 месяцев),
    // а не просто обрезать последние 18 точек данных (slice(-18)).
    const now = new Date();
    const base = now.getFullYear() * 12 + now.getMonth();
    const months = Array.from({ length: 15 }, (_, i) => {
      const total = base - 30 + i;
      const year = Math.floor(total / 12);
      const month = (total % 12) + 1;
      return { month: formatMonthLabel(month, year), light: i * 10, dark: i * 8 };
    });
    const { container } = render(<ActiveStudentsChart data={{ months }} />);
    const figcaption = container.querySelector('figcaption');
    expect(figcaption.textContent).toContain('18');
  });

  it('renders figcaption with month count', () => {
    const data = {
      months: [
        { month: 'Январь 2026', light: 100, dark: 80 },
        { month: 'Февраль 2026', light: 150, dark: 120 },
      ],
    };
    const { container } = render(<ActiveStudentsChart data={data} />);
    const figcaption = container.querySelector('figcaption');
    expect(figcaption.textContent).toContain('18');
  });
});
