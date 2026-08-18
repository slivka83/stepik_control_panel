import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SyncContext } from '../contexts/SyncContext';
import { AuthProvider } from '../contexts/AuthContext';
import Certificates from '../pages/Certificates';

const mockStats = {
  months: [
    { month: 'Июль 2026', total: 3, distinction: 1, regular: 2, students: 3 },
    { month: 'Август 2026', total: 2, distinction: 1, regular: 1, students: 1 },
  ],
  years: [{ year: 2026, total: 5, distinction: 2, regular: 3, students: 3 }],
  by_course: [
    { course_id: 'c1', stepik_course_id: 100, title: 'Python', total: 3, distinction: 1, regular: 2, students: 3 },
    { course_id: 'c2', stepik_course_id: 200, title: 'Java', total: 2, distinction: 1, regular: 1, students: 1 },
  ],
  totals: { certificates: 5, students: 3, distinction: 2, regular: 3 },
};

const makeSyncValue = (stats = mockStats) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {},
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses: [],
    certificatesStats: stats,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  selectedCourseIds: null,
  isFilterActive: false,
});

function renderCertificates(stats) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={makeSyncValue(stats)}>
          <Certificates />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Certificates', () => {
  it('renders KPI cards from totals', async () => {
    renderCertificates();
    expect(screen.getByText('Всего сертификатов')).toBeInTheDocument();
    expect(screen.getAllByText('Студенты').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('С отличием').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Обычные').length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText('5')).toBeInTheDocument();
  });

  it('renders months tab by default', () => {
    renderCertificates();
    expect(screen.getByText('2026 Июль')).toBeInTheDocument();
    expect(screen.getByText('2026 Август')).toBeInTheDocument();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('renders all three tabs', () => {
    renderCertificates();
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('По годам')).toBeInTheDocument();
    expect(screen.getByText('По курсам')).toBeInTheDocument();
  });

  it('switches to years tab on click', async () => {
    const user = userEvent.setup();
    renderCertificates();
    await user.click(screen.getByText('По годам'));
    expect(screen.getByText('2026')).toBeInTheDocument();
    expect(screen.getByText('Год')).toBeInTheDocument();
  });

  it('switches to courses tab and shows course links', async () => {
    const user = userEvent.setup();
    renderCertificates();
    await user.click(screen.getByText('По курсам'));
    const pythonLink = screen.getByText('Python');
    expect(pythonLink).toBeInTheDocument();
    expect(pythonLink.closest('a')).toHaveAttribute('href', 'https://stepik.org/course/100/certificates');
    expect(screen.getByText('Java')).toBeInTheDocument();
  });

  it('shows empty state when no data', () => {
    renderCertificates({
      months: [],
      years: [],
      by_course: [],
      totals: { certificates: 0, students: 0, distinction: 0, regular: 0 },
    });
    expect(screen.getByText('Нет данных')).toBeInTheDocument();
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(4);
  });

  it('shows 0 KPI values when stats missing', () => {
    renderCertificates(null);
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBeGreaterThanOrEqual(4);
  });

  it('shows chart toggle only on months tab', async () => {
    const user = userEvent.setup();
    renderCertificates();
    expect(screen.getByRole('button', { name: 'Показать график' })).toBeInTheDocument();
    await user.click(screen.getByText('По годам'));
    expect(screen.queryByRole('button', { name: 'Показать график' })).not.toBeInTheDocument();
  });

  it('toggles certificates table to bar chart and back', async () => {
    const user = userEvent.setup();
    renderCertificates();
    await user.click(screen.getByRole('button', { name: 'Показать график' }));
    expect(screen.getByRole('combobox', { name: 'Метрика графика' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Диаграмма С отличием / Обычные' })).toBeInTheDocument();
    expect(screen.queryByText('Месяц')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Показать таблицу' }));
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('switches certificates chart metric via the select', async () => {
    const user = userEvent.setup();
    renderCertificates();
    await user.click(screen.getByRole('button', { name: 'Показать график' }));
    const select = screen.getByRole('combobox', { name: 'Метрика графика' });
    await user.selectOptions(select, 'total');
    expect(screen.getByRole('img', { name: 'Диаграмма Всего' })).toBeInTheDocument();
  });
});
