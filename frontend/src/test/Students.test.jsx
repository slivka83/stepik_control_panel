import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import TestRouter from './TestRouter';
import Students from '../pages/Students';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}));

const makeSyncValue = (cohorts = { active: 0, passive: 0, fading: 0, sleeping: 0 }, extra = {}) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {},
    cohorts,
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials: null,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  selectedCourseIds: extra.selectedCourseIds ?? null,
  isFilterActive: extra.isFilterActive ?? false,
});

const makeStudent = (overrides = {}) => ({
  student_id: 123,
  name: 'Иван Петров',
  profile_url: 'https://stepik.org/users/123',
  cohort_status: 'Active',
  courses_count: 1,
  certificates: 0,
  submissions_count: 10,
  submissions_successful: 5,
  comments_count: 2,
  published_solutions: 0,
  last_activity: '2024-01-15T10:00:00Z',
  ...overrides,
});

const NUMERIC_SORT_KEYS = new Set([
  'courses_count',
  'certificates',
  'submissions_count',
  'comments_count',
  'published_solutions',
]);

// Mimics the server-side sort + pagination of /dashboard/students.
function applyServerSort(list, key, dir) {
  const mul = dir === 'desc' ? -1 : 1;
  return [...list].sort((a, b) => {
    if (key === 'last_activity') {
      if (a.last_activity == null && b.last_activity == null) return 0;
      if (a.last_activity == null) return 1;
      if (b.last_activity == null) return -1;
      return (new Date(a.last_activity) - new Date(b.last_activity)) * mul;
    }
    if (NUMERIC_SORT_KEYS.has(key)) return (a[key] - b[key]) * mul;
    return String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'ru') * mul;
  });
}

function mockStudentsApi(all) {
  api.get.mockImplementation((_url, config = {}) => {
    const { skip = 0, limit = all.length, sort = 'last_activity', order = 'desc' } = config.params || {};
    const sorted = applyServerSort(all, sort, order);
    return Promise.resolve({ data: { students: sorted.slice(skip, skip + limit), total: all.length } });
  });
}

describe('Students', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockResolvedValue({ data: { students: [], total: 0 } });
  });

  it('renders all four cohort labels', () => {
    render(
      <TestRouter syncValue={makeSyncValue({ active: 100, passive: 50, fading: 30, sleeping: 20 })}>
        <Students />
      </TestRouter>,
    );
    expect(screen.getByText('Активные')).toBeInTheDocument();
    expect(screen.getByText('Пассивные')).toBeInTheDocument();
    expect(screen.getByText('Затухающие')).toBeInTheDocument();
    expect(screen.getByText('Спящие')).toBeInTheDocument();
  });

  it('renders cohort percentages', () => {
    render(
      <TestRouter syncValue={makeSyncValue({ active: 50, passive: 50, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    expect(screen.getAllByText(/%/).length).toBeGreaterThanOrEqual(2);
  });

  it('renders student table with no data message', async () => {
    render(
      <TestRouter syncValue={makeSyncValue()}>
        <Students />
      </TestRouter>,
    );
    expect(await screen.findByText('Нет данных о студентах')).toBeInTheDocument();
  });

  it('does not render list header and total counter', () => {
    render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    expect(screen.queryByText('Список студентов')).not.toBeInTheDocument();
    expect(screen.queryByText('7677 всего')).not.toBeInTheDocument();
  });

  it('renders aggregated student rows', async () => {
    mockStudentsApi([
      makeStudent({
        student_id: 123,
        name: 'Иван Петров',
        cohort_status: 'Active',
        courses_count: 2,
        certificates: 1,
        submissions_count: 15,
        comments_count: 3,
      }),
      makeStudent({
        student_id: 456,
        name: null,
        cohort_status: 'Passive',
        courses_count: 1,
        certificates: 0,
        submissions_count: 0,
        comments_count: 0,
      }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 1, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    expect(await screen.findByText('Иван Петров')).toBeInTheDocument();
    expect(screen.getByText('Студент 456')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Passive')).toBeInTheDocument();
  });

  it('links student name to profile', async () => {
    mockStudentsApi([
      makeStudent({ student_id: 777, profile_url: 'https://stepik.org/users/777', name: 'Мария Смирнова' }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    const link = (await screen.findByText('Мария Смирнова')).closest('a');
    expect(link).toHaveAttribute('href', 'https://stepik.org/users/777');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders aggregated counters', async () => {
    mockStudentsApi([
      makeStudent({
        student_id: 123,
        courses_count: 3,
        certificates: 2,
        submissions_count: 42,
        submissions_successful: 23,
        comments_count: 7,
        published_solutions: 5,
      }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    expect(await screen.findByText('42 (55%)')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders zero submissions without percentage', async () => {
    mockStudentsApi([makeStudent({ student_id: 123, submissions_count: 0, submissions_successful: 0 })]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    await waitFor(() => expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(2));
    expect(screen.queryByText(/\(%/)).not.toBeInTheDocument();
  });

  it('right-aligns activity header and cells', async () => {
    mockStudentsApi([makeStudent()]);
    const { container } = render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    await screen.findByText('Иван Петров');
    const header = screen.getByText('Активность').closest('th');
    expect(header.className).toContain('text-right');
    const cell = container.querySelector('td.whitespace-nowrap');
    expect(cell.className).toContain('text-right');
  });

  it('renders without crashing when no data', () => {
    const { container } = render(
      <TestRouter syncValue={makeSyncValue()}>
        <Students />
      </TestRouter>,
    );
    expect(container.querySelector('[class*="flex"]')).toBeInTheDocument();
  });

  it('sorts by Курсы on header click', async () => {
    mockStudentsApi([
      makeStudent({ student_id: 1, name: 'А', courses_count: 1 }),
      makeStudent({ student_id: 2, name: 'Б', courses_count: 5 }),
      makeStudent({ student_id: 3, name: 'В', courses_count: 3 }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 3, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );

    const header = screen.getByText('Курсы').closest('th');
    fireEvent.click(header);

    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1);
      expect(within(rows[0]).getByText('Б')).toBeInTheDocument();
      expect(within(rows[2]).getByText('А')).toBeInTheDocument();
    });
    expect(api.get).toHaveBeenLastCalledWith('/dashboard/students', {
      params: expect.objectContaining({ sort: 'courses_count', order: 'desc' }),
    });

    fireEvent.click(header);

    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1);
      expect(within(rows[0]).getByText('А')).toBeInTheDocument();
      expect(within(rows[2]).getByText('Б')).toBeInTheDocument();
    });
  });

  it('renders published solutions column', async () => {
    mockStudentsApi([
      makeStudent({ student_id: 1, name: 'С решением', published_solutions: 4 }),
      makeStudent({ student_id: 2, name: 'Без решений', published_solutions: 0 }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 2, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    expect(await screen.findByText('С решением')).toBeInTheDocument();
    expect(screen.getByText('Опубликованные')).toBeInTheDocument();
    const cell = screen.getByText('4');
    expect(cell.className).toContain('text-right');
  });

  it('sorts by Опубликованные on header click', async () => {
    mockStudentsApi([
      makeStudent({ student_id: 1, name: 'А', published_solutions: 1 }),
      makeStudent({ student_id: 2, name: 'Б', published_solutions: 5 }),
      makeStudent({ student_id: 3, name: 'В', published_solutions: 3 }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 3, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );

    fireEvent.click(screen.getByText('Опубликованные').closest('th'));

    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1);
      expect(within(rows[0]).getByText('Б')).toBeInTheDocument();
      expect(within(rows[2]).getByText('А')).toBeInTheDocument();
    });
    expect(api.get).toHaveBeenLastCalledWith('/dashboard/students', {
      params: expect.objectContaining({ sort: 'published_solutions', order: 'desc' }),
    });
  });

  it('sorts by Имя on header click (alphabetical)', async () => {
    mockStudentsApi([
      makeStudent({ student_id: 1, name: 'Иван Петров' }),
      makeStudent({ student_id: 2, name: 'Анна Иванова' }),
      makeStudent({ student_id: 3, name: 'Олег Сидоров' }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 3, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );

    fireEvent.click(screen.getByText('Имя').closest('th'));

    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1);
      expect(within(rows[0]).getByText('Анна Иванова')).toBeInTheDocument();
      expect(within(rows[1]).getByText('Иван Петров')).toBeInTheDocument();
      expect(within(rows[2]).getByText('Олег Сидоров')).toBeInTheDocument();
    });
  });

  it('sorts by Активность — newest first by default, oldest after click', async () => {
    mockStudentsApi([
      makeStudent({ student_id: 1, name: 'Старый', last_activity: '2024-01-01T00:00:00Z' }),
      makeStudent({ student_id: 2, name: 'Новый', last_activity: '2026-01-01T00:00:00Z' }),
      makeStudent({ student_id: 3, name: 'Средний', last_activity: '2025-01-01T00:00:00Z' }),
    ]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 3, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );

    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1);
      expect(within(rows[0]).getByText('Новый')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Активность').closest('th'));

    await waitFor(() => {
      const rows = screen.getAllByRole('row').slice(1);
      expect(within(rows[0]).getByText('Старый')).toBeInTheDocument();
    });
  });

  it('paginates students via the server', async () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...makeStudent({ student_id: i + 1, name: `Студент ${i + 1}` }),
    }));
    mockStudentsApi(many);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 20, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );

    expect(await screen.findByText('Страница 1 из 2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Вперёд →'));
    expect(await screen.findByText('Страница 2 из 2')).toBeInTheDocument();
    expect(screen.queryByText('Студент 1')).not.toBeInTheDocument();
    expect(api.get).toHaveBeenLastCalledWith('/dashboard/students', {
      params: expect.objectContaining({ skip: 18, limit: 18 }),
    });
  });

  it('resets to page 1 when sorting from a later page', async () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...makeStudent({ student_id: i + 1, name: `Студент ${i + 1}`, courses_count: (i % 3) + 1 }),
    }));
    mockStudentsApi(many);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 20, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );

    expect(await screen.findByText('Страница 1 из 2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Вперёд →'));
    expect(await screen.findByText('Страница 2 из 2')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Курсы').closest('th'));

    await waitFor(() => {
      expect(api.get).toHaveBeenLastCalledWith('/dashboard/students', {
        params: expect.objectContaining({ skip: 0, limit: expect.any(Number), sort: 'courses_count', order: 'desc' }),
      });
    });
    expect(await screen.findByText('Страница 1 из 2')).toBeInTheDocument();
  });

  it('renders activity date in dd.mm.yyyy format like Опубликован on Courses', async () => {
    mockStudentsApi([makeStudent({ last_activity: '2024-01-15T10:00:00Z' })]);
    render(
      <TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 })}>
        <Students />
      </TestRouter>,
    );
    expect(await screen.findByText('15.01.2024')).toBeInTheDocument();
  });

  it('passes course_ids to the students fetch when a filter is active', async () => {
    mockStudentsApi([makeStudent()]);
    render(
      <TestRouter
        syncValue={makeSyncValue(
          { active: 1, passive: 0, fading: 0, sleeping: 0 },
          { selectedCourseIds: ['u1', 'u2'], isFilterActive: true },
        )}
      >
        <Students />
      </TestRouter>,
    );
    await screen.findByText('Иван Петров');
    expect(api.get).toHaveBeenLastCalledWith('/dashboard/students', {
      params: expect.objectContaining({ course_ids: 'u1,u2' }),
    });
  });
});
