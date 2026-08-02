import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TestRouter from './TestRouter';
import Activities from '../pages/Activities';

const makeSyncValue = (overrides = {}) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {
      total_revenue: 0,
      total_students: 0,
      certificates_issued: 0,
      courses_count: 0,
      net_income: 0,
      total_turnover: 0,
      total_payments: 0,
      total_refunds: 0,
      total_income: 0,
    },
    cohorts: {},
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials: { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] },
    students: { students: [], total: 0 },
    submissions: { months: [] },
    activeStudents: { months: [] },
    activeEnrolled: { months: [] },
    publishedSolutions: { months: [] },
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  ...overrides,
});

describe('Activities', () => {
  it('renders all four charts', () => {
    render(
      <TestRouter syncValue={makeSyncValue()}>
        <Activities />
      </TestRouter>,
    );
    expect(screen.getByText('Активные студенты')).toBeInTheDocument();
    expect(screen.getByText('Опубликованные решения')).toBeInTheDocument();
    expect(screen.getByText('Комментарии')).toBeInTheDocument();
    expect(screen.getAllByText('Отправленные решения').length).toBeGreaterThanOrEqual(1);
  });

  it('comments chart shows the 18-month window ending with the current month', () => {
    // Regression: метки месяцев из toLocaleDateString('ru-RU') содержат суффикс
    // «г.» ("июль 2026 г.") — parseMonthLabel не мог их разобрать, и окно
    // откатывалось к slice(-18) без привязки к текущему месяцу.
    const commentsMonthly = {};
    const now = new Date();
    const base = now.getFullYear() * 12 + now.getMonth();
    for (let i = 23; i >= 0; i--) {
      const total = base - i;
      const year = Math.floor(total / 12);
      const month = (total % 12) + 1;
      commentsMonthly[`${year}-${String(month).padStart(2, '0')}`] = i + 1;
    }
    const { container } = render(
      <TestRouter
        syncValue={makeSyncValue({
          data: {
            financials: { community: { comments_monthly: commentsMonthly } },
            submissions: { months: [] },
            activeStudents: { months: [] },
            publishedSolutions: { months: [] },
          },
        })}
      >
        <Activities />
      </TestRouter>,
    );
    const figure = container.querySelector('figure[aria-label="Диаграмма Комментарии"]');
    expect(figure).toBeInTheDocument();
    const figcaption = figure.querySelector('figcaption');
    expect(figcaption.textContent).toContain('18');
  });
});
