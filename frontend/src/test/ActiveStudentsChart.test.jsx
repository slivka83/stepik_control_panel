import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ActiveStudentsChart, { darkTooltipValue } from '../components/ActiveStudentsChart';
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

  it('uses lightLabel and darkLabel in the legend', () => {
    const data = { months: [{ month: 'Январь 2026', light: 10, dark: 12 }] };
    render(<ActiveStudentsChart data={data} lightLabel="Обычные" darkLabel="С отличием" />);
    expect(screen.getByText('Обычные')).toBeInTheDocument();
    expect(screen.getByText('С отличием')).toBeInTheDocument();
    expect(screen.queryByText('Уникальные по курсам')).not.toBeInTheDocument();
  });

  it('darkTooltipOverlap shows the overlap value in the tooltip', () => {
    // Regression: для сертификатов dark = всего, overlap = «С отличием»
    // (dark − light) — тултип обязан показывать именно overlap, а не dark.
    const entry = { month: 'Январь 2026', light: 10, dark: 13 };
    expect(darkTooltipValue(entry, true)).toBe(3);
    expect(darkTooltipValue(entry, false)).toBe(13);
    expect(darkTooltipValue({ light: 5, dark: 2 }, true)).toBe(0);
    expect(darkTooltipValue({ light: 5 }, false)).toBe(0);
  });
});
