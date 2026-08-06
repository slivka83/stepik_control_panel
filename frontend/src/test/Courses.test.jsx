import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import TestRouter from './TestRouter';
import Courses from '../pages/Courses';

vi.mock('react-countup', () => ({
  default: ({ end, formattingFn }) => <span>{formattingFn ? formattingFn(end) : end}</span>,
}));

const defaultCourse = {
  id: '1',
  title: 'C1',
  status: 'Published',
  stepik_course_id: 100,
  enrollment_count: 50,
  certificates_count: 100,
  comments_count: 30,
  reviews_count: 10,
  average_rating: 4.5,
  income: 5000,
};

const makeSyncValue = (courses = [], extra = {}) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {
      total_revenue: 0,
      total_students: 0,
      certificates_issued: 0,
      courses_count: courses.length,
      courses_published: courses.filter((c) => c.status === 'Published').length,
      courses_unpublished: courses.filter((c) => c.status !== 'Published').length,
      net_income: 0,
      total_turnover: 0,
      total_payments: 0,
      total_refunds: 0,
      total_income: 0,
      total_comments: 0,
      average_rating: 0,
    },
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses,
    financials: { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] },
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  selectedCourseIds: extra.selectedCourseIds ?? null,
  isFilterActive: extra.isFilterActive ?? false,
});

describe('Courses', () => {
  it('renders KPI cards', () => {
    render(
      <TestRouter syncValue={makeSyncValue([defaultCourse])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Всего курсов')).toBeInTheDocument();
    expect(screen.getByText('Опубликовано')).toBeInTheDocument();
    expect(screen.getByText('Черновиков')).toBeInTheDocument();
  });

  it('renders published and draft card numbers in white like dashboard', () => {
    render(
      <TestRouter syncValue={makeSyncValue([defaultCourse])}>
        <Courses />
      </TestRouter>,
    );
    for (const title of ['Опубликовано', 'Черновиков']) {
      const card = screen.getByText(title).closest('.glass-panel');
      expect(card.querySelector('.font-mono')).toHaveClass('text-gray-300');
    }
  });

  it('does not render total comments card', () => {
    render(
      <TestRouter syncValue={makeSyncValue([defaultCourse])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.queryByText('Всего комментариев')).not.toBeInTheDocument();
  });

  it('shows empty state with connect button', () => {
    render(
      <TestRouter syncValue={makeSyncValue()}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Нет курсов')).toBeInTheDocument();
    expect(screen.getByText('Подключить Stepik')).toBeInTheDocument();
  });

  it('renders course title in table', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, title: 'Python Course' }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Python Course')).toBeInTheDocument();
  });

  it('renders enrollment count', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, enrollment_count: 42 }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getAllByText('42').length).toBeGreaterThanOrEqual(1);
  });

  it('renders comments count', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, comments_count: 15 }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  it('renders certificates count', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, certificates_count: 7 }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getAllByText('7').length).toBeGreaterThanOrEqual(1);
  });

  it('renders Сертификаты column header', () => {
    render(
      <TestRouter syncValue={makeSyncValue([defaultCourse])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Сертификаты')).toBeInTheDocument();
  });

  it('renders Опубликован status', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, status: 'Published' }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getAllByText('Опубликован').length).toBeGreaterThanOrEqual(1);
  });

  it('renders Черновик status', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, status: 'Draft' }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Черновик')).toBeInTheDocument();
  });

  it('renders Stepik deep link', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, stepik_course_id: 12345 }])}>
        <Courses />
      </TestRouter>,
    );
    const link = screen.getByText('C1').closest('a');
    expect(link).toHaveAttribute('href', 'https://stepik.org/course/12345');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('renders multiple courses', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue([
          { ...defaultCourse, id: '1', title: 'Python' },
          { ...defaultCourse, id: '2', title: 'JS' },
          { ...defaultCourse, id: '3', title: 'ML' },
        ])}
      >
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('JS')).toBeInTheDocument();
    expect(screen.getByText('ML')).toBeInTheDocument();
  });

  it('renders table headers', () => {
    render(
      <TestRouter syncValue={makeSyncValue([defaultCourse])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Название')).toBeInTheDocument();
    expect(screen.getByText('Статус')).toBeInTheDocument();
    expect(screen.getByText('Стоимость')).toBeInTheDocument();
    expect(screen.getAllByText('Опубликован').length).toBeGreaterThanOrEqual(1);
  });

  it('renders price', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, price: 2990 }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText(/990/)).toBeInTheDocument();
  });

  it('renders price as dash when null', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, price: null }])}>
        <Courses />
      </TestRouter>,
    );
    const dashes = screen.getAllByText('—');
    expect(dashes.length).toBeGreaterThanOrEqual(1);
  });

  it('renders published_at date', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, published_at: '2024-06-15T10:00:00Z' }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText(/2024/)).toBeInTheDocument();
  });

  it('renders rating with color', () => {
    render(
      <TestRouter syncValue={makeSyncValue([{ ...defaultCourse, average_rating: 4.5 }])}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('4.50')).toBeInTheDocument();
  });

  it('sorts by Студенты on header click', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue([
          { ...defaultCourse, id: '1', title: 'Low', enrollment_count: 5 },
          { ...defaultCourse, id: '2', title: 'High', enrollment_count: 500 },
          { ...defaultCourse, id: '3', title: 'Mid', enrollment_count: 50 },
        ])}
      >
        <Courses />
      </TestRouter>,
    );

    const header = screen.getByText('Студенты').closest('th');
    fireEvent.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('High')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Low')).toBeInTheDocument();

    fireEvent.click(header);
    const rowsAsc = screen.getAllByRole('row').slice(1);
    expect(within(rowsAsc[0]).getByText('Low')).toBeInTheDocument();
    expect(within(rowsAsc[2]).getByText('High')).toBeInTheDocument();
  });

  it('keeps drafts last when sorting by Опубликован desc', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue([
          { ...defaultCourse, id: '1', title: 'Draft', published_at: null },
          { ...defaultCourse, id: '2', title: 'Old', published_at: '2024-01-01T00:00:00Z' },
          { ...defaultCourse, id: '3', title: 'New', published_at: '2026-07-01T00:00:00Z' },
        ])}
      >
        <Courses />
      </TestRouter>,
    );

    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('New')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Old')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Draft')).toBeInTheDocument();
  });

  it('ignores course filter — renders all courses when a subset is selected', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue(
          [
            { ...defaultCourse, id: '1', title: 'Python' },
            { ...defaultCourse, id: '2', title: 'JS' },
            { ...defaultCourse, id: '3', title: 'ML' },
          ],
          { selectedCourseIds: ['1'], isFilterActive: true },
        )}
      >
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('JS')).toBeInTheDocument();
    expect(screen.getByText('ML')).toBeInTheDocument();
  });

  it('ignores course filter — renders table, not "Нет курсов", when nothing is selected', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue([defaultCourse], { selectedCourseIds: [], isFilterActive: true })}
      >
        <Courses />
      </TestRouter>,
    );
    expect(screen.queryByText('Нет курсов')).not.toBeInTheDocument();
    expect(screen.queryByText('Подключить Stepik')).not.toBeInTheDocument();
    expect(screen.getByText('C1')).toBeInTheDocument();
  });

  it('computes KPI cards from the full course list regardless of the filter', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue(
          [
            { ...defaultCourse, id: '1', title: 'Published A', status: 'Published', enrollment_count: 30 },
            { ...defaultCourse, id: '2', title: 'Draft B', status: 'Draft', enrollment_count: 12 },
          ],
          { selectedCourseIds: ['1'], isFilterActive: true },
        )}
      >
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Всего курсов').closest('.glass-panel').textContent).toContain('2');
    expect(screen.getByText('Опубликовано').closest('.glass-panel').textContent).toContain('1');
    expect(screen.getByText('Черновиков').closest('.glass-panel').textContent).toContain('1');
    expect(screen.getByText('Всего студентов').closest('.glass-panel').textContent).toContain('42');
    expect(
      screen.getAllByText('Доход').some((el) => el.closest('.glass-panel')?.textContent.includes('10\u00A0000')),
    ).toBe(true);
  });

  it('Regression: average rating ignores courses without reviews (0 rating)', () => {
    render(
      <TestRouter
        syncValue={makeSyncValue([
          { ...defaultCourse, id: '1', title: 'Rated', average_rating: 4.5 },
          { ...defaultCourse, id: '2', title: 'No reviews', average_rating: 0 },
        ])}
      >
        <Courses />
      </TestRouter>,
    );
    const card = screen.getByText('Средний рейтинг').closest('.glass-panel');
    expect(card.textContent).toContain('4,50');
    expect(card.textContent).not.toContain('2,25');
  });

  it('shows arrow pointing at the anchor values (up on first click, down on second)', () => {
    render(
      <TestRouter syncValue={makeSyncValue([defaultCourse])}>
        <Courses />
      </TestRouter>,
    );
    const arrowOf = (th) => th.querySelector('span.text-cyber-blue').textContent;
    expect(arrowOf(screen.getAllByText('Опубликован')[0].closest('th'))).toBe('↑');

    const header = screen.getByText('Студенты').closest('th');
    fireEvent.click(header);
    expect(arrowOf(header)).toBe('↑');
    fireEvent.click(header);
    expect(arrowOf(header)).toBe('↓');
    fireEvent.click(header);
    expect(arrowOf(header)).toBe('↑');
  });

  it('paginates courses', () => {
    const many = Array.from({ length: 20 }, (_, i) => ({
      ...defaultCourse,
      id: String(i + 1),
      title: `Курс ${i + 1}`,
    }));
    render(
      <TestRouter syncValue={makeSyncValue(many)}>
        <Courses />
      </TestRouter>,
    );
    expect(screen.getByText('Страница 1 из 2')).toBeInTheDocument();
    fireEvent.click(screen.getByText('Вперёд →'));
    expect(screen.getByText('Страница 2 из 2')).toBeInTheDocument();
    expect(screen.queryByText('Курс 1')).not.toBeInTheDocument();
  });
});
