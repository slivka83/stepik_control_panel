import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import TestRouter from './TestRouter';
import Dashboard from '../pages/Dashboard';

const mockKpi = {
  total_revenue: 50000,
  revenue_change_pct: 12,
  current_month_payments: 55,
  payments_change_pct: 8,
  current_month_refunds_count: 21930,
  refunds_change_pct: -3,
  courses_published: 5,
  courses_unpublished: 2,
  students_prev_months: 7563,
  current_month_students: 55,
  students_change_pct: 45,
  average_rating: 4.95,
  current_month_submissions: 8123,
  submissions_change_pct: 10,
  reviews_prev_months: 20,
  reviews_current_month: 0,
  reviews_change_pct: 0,
  current_month_comments: 71,
  comments_change_pct: 318,
  comments_prev_months: 1490,
  published_solutions_prev_months: 96,
  published_solutions_current_month: 5,
  published_solutions_change_pct: 25,
  certificates_prev_months: 178,
  certificates_current_month: 7,
  certificates_change_pct: 133,
  steps_average_grade: 4.7,
};

const mockCohorts = { active: 7000, passive: 400, fading: 200, sleeping: 18 };

const mockRevenue = {
  months: [
    { month: '2026-01-01T00:00:00', revenue: 12000 },
    { month: '2026-02-01T00:00:00', revenue: 18000 },
  ],
};

const fullSyncValue = {
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: mockKpi,
    cohorts: mockCohorts,
    revenue: mockRevenue,
    alerts: [],
    courses: [],
    financials: { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] },
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
};

const zeroKpi = {
  total_revenue: 0,
  revenue_change_pct: null,
  current_month_payments: 0,
  payments_change_pct: null,
  current_month_refunds_count: 0,
  refunds_change_pct: null,
  courses_published: 0,
  courses_unpublished: 0,
  students_prev_months: 0,
  current_month_students: 0,
  students_change_pct: null,
  average_rating: 0,
  current_month_submissions: 0,
  submissions_change_pct: null,
  reviews_prev_months: 0,
  reviews_current_month: 0,
  reviews_change_pct: null,
  current_month_comments: 0,
  comments_change_pct: null,
  comments_prev_months: 0,
  published_solutions_prev_months: 0,
  published_solutions_current_month: 0,
  published_solutions_change_pct: null,
  certificates_prev_months: 0,
  certificates_current_month: 0,
  certificates_change_pct: null,
  steps_average_grade: 0,
};

const KPI_TITLES = [
  'Доход /месяц',
  'Покупки /месяц',
  'Возвраты /месяц',
  'Курсы',
  'Средний рейтинг курсов',
  'Решения /месяц',
  'Отзывы',
  'Публичные решения',
  'Комментарии',
  'Сертификаты',
  'Средняя оценка шагов',
];

async function cardByTrend(trendText, index = 0) {
  const trend = (await screen.findAllByText(trendText))[index];
  return trend.closest('.glass-panel');
}

describe('Dashboard', () => {
  it('renders all twelve KPI cards', () => {
    render(
      <TestRouter syncValue={fullSyncValue}>
        <Dashboard />
      </TestRouter>,
    );
    [...KPI_TITLES, 'Студенты'].forEach((t) => {
      expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    });
  });

  it('renders previous months + current month split with trend', async () => {
    render(
      <TestRouter syncValue={fullSyncValue}>
        <Dashboard />
      </TestRouter>,
    );

    const studentsCard = await cardByTrend('↑ 45%');
    await waitFor(() => expect(studentsCard.textContent).toContain('+55'), { timeout: 4000 });

    const commentsCard = await cardByTrend('↑ 318%');
    await waitFor(() => expect(commentsCard.textContent).toContain('+71'), { timeout: 4000 });

    const solutionsCard = await cardByTrend('↑ 25%');
    await waitFor(() => expect(solutionsCard.textContent).toContain('+5'), { timeout: 4000 });

    const certsCard = await cardByTrend('↑ 133%');
    await waitFor(() => expect(certsCard.textContent).toContain('+7'), { timeout: 4000 });

    expect(await screen.findByText('4,95')).toBeInTheDocument();
    expect(await screen.findByText('4,70')).toBeInTheDocument();
  });

  it('renders with zero KPI values', () => {
    const zeroValue = {
      ...fullSyncValue,
      data: {
        ...fullSyncValue.data,
        kpi: zeroKpi,
        cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
        revenue: { months: [] },
      },
    };
    render(
      <TestRouter syncValue={zeroValue}>
        <Dashboard />
      </TestRouter>,
    );
    [...KPI_TITLES, 'Студенты'].forEach((t) => {
      expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    });
  });

  it('renders chart sections', () => {
    render(
      <TestRouter syncValue={fullSyncValue}>
        <Dashboard />
      </TestRouter>,
    );
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument();
    expect(screen.getByText('Отправленные решения')).toBeInTheDocument();
  });

  it('renders KPI cards and charts while loading (no skeleton placeholders)', () => {
    const { container } = render(
      <TestRouter syncValue={{ ...fullSyncValue, loading: true, data: { ...fullSyncValue.data, kpi: null } }}>
        <Dashboard />
      </TestRouter>,
    );
    expect(screen.queryByText(/Загрузка/)).not.toBeInTheDocument();
    expect(container.querySelectorAll('.animate-pulse').length).toBe(0);
    expect(screen.getAllByText(/Доход/).length).toBeGreaterThanOrEqual(1);
  });

  it('shows error banner on failure', () => {
    render(
      <TestRouter syncValue={{ ...fullSyncValue, error: 'Network error' }}>
        <Dashboard />
      </TestRouter>,
    );
    expect(screen.getByText('Ошибка загрузки данных')).toBeInTheDocument();
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });
});
