import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SyncContext } from '../contexts/SyncContext';
import { AuthProvider } from '../contexts/AuthContext';
import Reviews from '../pages/Reviews';

const mockStats = {
  months: [
    { month: 'Июль 2026', total: 3, avg_score: 4.5, students: 3 },
    { month: 'Август 2026', total: 2, avg_score: 4.0, students: 1 },
  ],
  years: [{ year: 2026, total: 5, avg_score: 4.25, students: 3 }],
  by_course: [
    { course_id: 'c1', stepik_course_id: 100, title: 'Python', total: 3, avg_score: 4.5, students: 3 },
    { course_id: 'c2', stepik_course_id: 200, title: 'Java', total: 2, avg_score: 4.0, students: 1 },
  ],
  totals: { reviews: 5, students: 3, avg_score: 4.25 },
};

const makeSyncValue = (stats = mockStats) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {},
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses: [],
    reviewsStats: stats,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  selectedCourseIds: null,
  isFilterActive: false,
});

function renderReviews(stats) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={makeSyncValue(stats)}>
          <Reviews />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Reviews', () => {
  it('renders KPI cards from totals', async () => {
    renderReviews();
    expect(screen.getByText('Всего отзывов')).toBeInTheDocument();
    expect(screen.getAllByText('Студенты').length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText('5')).toBeInTheDocument();
  });

  it('renders average score KPI', async () => {
    renderReviews();
    expect(screen.getAllByText('Средняя оценка').length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText('4,25', {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it('renders months tab by default', () => {
    renderReviews();
    expect(screen.getByText('2026 Июль')).toBeInTheDocument();
    expect(screen.getByText('2026 Август')).toBeInTheDocument();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('renders all three tabs', () => {
    renderReviews();
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('По годам')).toBeInTheDocument();
    expect(screen.getByText('По курсам')).toBeInTheDocument();
  });

  it('switches to years tab on click', async () => {
    const user = userEvent.setup();
    renderReviews();
    await user.click(screen.getByText('По годам'));
    expect(screen.getByText('2026')).toBeInTheDocument();
    expect(screen.getByText('Год')).toBeInTheDocument();
  });

  it('switches to courses tab and shows course links', async () => {
    const user = userEvent.setup();
    renderReviews();
    await user.click(screen.getByText('По курсам'));
    const pythonLink = screen.getByText('Python');
    expect(pythonLink).toBeInTheDocument();
    expect(pythonLink.closest('a')).toHaveAttribute('href', 'https://stepik.org/course/100');
    expect(screen.getByText('Java')).toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    renderReviews({
      months: [],
      years: [],
      by_course: [],
      totals: { reviews: 0, students: 0, avg_score: 0 },
    });
    expect(screen.getByText('Нет данных')).toBeInTheDocument();
  });

  it('shows 0 KPI values when stats missing', () => {
    renderReviews(null);
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBeGreaterThanOrEqual(3);
  });

  it('shows chart toggle only on months tab', async () => {
    const user = userEvent.setup();
    renderReviews();
    expect(screen.getByRole('button', { name: 'Показать график' })).toBeInTheDocument();
    await user.click(screen.getByText('По годам'));
    expect(screen.queryByRole('button', { name: 'Показать график' })).not.toBeInTheDocument();
  });

  it('toggles reviews table to bar chart and back', async () => {
    const user = userEvent.setup();
    renderReviews();
    await user.click(screen.getByRole('button', { name: 'Показать график' }));
    expect(screen.getByRole('combobox', { name: 'Метрика графика' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Диаграмма Отзывы' })).toBeInTheDocument();
    expect(screen.queryByText('Месяц')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Показать таблицу' }));
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('switches reviews chart metric via the select', async () => {
    const user = userEvent.setup();
    renderReviews();
    await user.click(screen.getByRole('button', { name: 'Показать график' }));
    const select = screen.getByRole('combobox', { name: 'Метрика графика' });
    await user.selectOptions(select, 'avg_score');
    expect(screen.getByRole('img', { name: 'Диаграмма Средняя оценка' })).toBeInTheDocument();
  });
});
