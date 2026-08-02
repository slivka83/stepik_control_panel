import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import SubmissionsChart from '../components/SubmissionsChart';

describe('SubmissionsChart', () => {
  it('renders empty state when no months data', () => {
    render(<SubmissionsChart data={{}} />);
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument();
  });

  it('renders chart title', () => {
    render(<SubmissionsChart data={{ months: [] }} />);
    expect(screen.getByText('Отправленные решения')).toBeInTheDocument();
  });

  it('renders with data', () => {
    const data = {
      months: [
        { month: 'Январь 2026', total: 100, correct: 80 },
        { month: 'Февраль 2026', total: 150, correct: 120 },
      ],
    };
    render(<SubmissionsChart data={data} />);
    expect(screen.getByText('Отправленные решения')).toBeInTheDocument();
    expect(screen.queryByText('Нет данных для отображения')).not.toBeInTheDocument();
  });

  it('renders glass-panel container', () => {
    const { container } = render(<SubmissionsChart data={{ months: [] }} />);
    expect(container.querySelector('.glass-panel')).toBeInTheDocument();
  });

  it('renders legend items', () => {
    const data = {
      months: [{ month: 'Январь 2026', total: 100, correct: 80 }],
    };
    render(<SubmissionsChart data={data} />);
    expect(screen.getByText('Правильные')).toBeInTheDocument();
    expect(screen.getByText('Всего')).toBeInTheDocument();
    expect(screen.getByText('не завершён')).toBeInTheDocument();
  });

  it('wraps chart in figure with aria-label', () => {
    const data = {
      months: [{ month: 'Январь 2026', total: 100, correct: 80 }],
    };
    const { container } = render(<SubmissionsChart data={data} />);
    const figure = container.querySelector('figure');
    expect(figure).toBeInTheDocument();
    expect(figure).toHaveAttribute('aria-label', 'Диаграмма решений по месяцам');
  });

  it('renders figcaption with month count', () => {
    const data = {
      months: [
        { month: 'Январь 2026', total: 100, correct: 80 },
        { month: 'Февраль 2026', total: 150, correct: 120 },
      ],
    };
    const { container } = render(<SubmissionsChart data={data} />);
    const figcaption = container.querySelector('figcaption');
    expect(figcaption).toBeInTheDocument();
    expect(figcaption.textContent).toContain('18');
  });

  it('shows the 18-month window ending with the current month', () => {
    const months = Array.from({ length: 25 }, (_, i) => ({
      month: `Месяц ${i + 1}`,
      total: i * 10,
      correct: i * 8,
    }));
    const { container } = render(<SubmissionsChart data={{ months }} />);
    const figcaption = container.querySelector('figcaption');
    expect(figcaption.textContent).toContain('18');
    expect(screen.getByText('Отправленные решения')).toBeInTheDocument();
  });

  it('renders with single month of data', () => {
    const data = {
      months: [{ month: 'Март 2026', total: 50, correct: 30 }],
    };
    render(<SubmissionsChart data={data} />);
    expect(screen.queryByText('Нет данных для отображения')).not.toBeInTheDocument();
  });

  it('handles zero correct submissions', () => {
    const data = {
      months: [{ month: 'Апрель 2026', total: 100, correct: 0 }],
    };
    render(<SubmissionsChart data={data} />);
    expect(screen.queryByText('Нет данных для отображения')).not.toBeInTheDocument();
  });
});
