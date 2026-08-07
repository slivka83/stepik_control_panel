import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SyncContext } from '../contexts/SyncContext';
import { AuthProvider } from '../contexts/AuthContext';
import Comments from '../pages/Comments';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}));

const mockComments = {
  months: [
    { month: 'Январь 2026', students: 6, total: 10, likes: 12, dislikes: 2, replies: 4 },
    { month: 'Февраль 2026', students: 9, total: 20, likes: 25, dislikes: 5, replies: 8 },
  ],
  years: [
    { year: 2026, students: 12, total: 30, likes: 37, dislikes: 7, replies: 12 },
    { year: 2025, students: 3, total: 5, likes: 4, dislikes: 1, replies: 2 },
  ],
  by_course: [
    { course_id: 1, stepik_course_id: 101, title: 'Тестовый курс', students: 11, total: 30, likes: 37, dislikes: 7, replies: 12 },
    { course_id: 2, stepik_course_id: 102, title: 'Алгоритмы', students: 2, total: 5, likes: 4, dislikes: 1, replies: 2 },
  ],
  totals: { comments: 35, students: 13, likes: 41, dislikes: 8, replies: 14 },
};

const mockList = {
  comments: [
    {
      comment_id: 101,
      time: '2026-07-10T10:00:00Z',
      user_id: 1,
      user_name: 'Иван Петров',
      course_id: 'c-uuid-1',
      course_title: 'Python',
      stepik_course_id: 101,
      text: 'Вопрос по лекции',
      likes: 3,
      dislikes: 0,
      replies: 1,
      lesson_id: 10,
      step_number: 1,
      module_number: 1,
      lesson_number: 1,
      module_title: 'Модуль 1',
      lesson_title: 'Урок 1',
    },
    {
      comment_id: 102,
      time: '2026-07-11T10:00:00Z',
      user_id: 2,
      user_name: null,
      course_id: 'c-uuid-2',
      course_title: 'Java',
      stepik_course_id: 102,
      text: 'Спасибо',
      likes: 0,
      dislikes: 2,
      replies: 0,
      lesson_id: null,
      step_number: null,
      module_number: null,
      lesson_number: null,
      module_title: null,
      lesson_title: null,
    },
  ],
  total: 2,
};

const makeSyncValue = (comments = mockComments, overrides = {}) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {},
    cohorts: {},
    revenue: { months: [] },
    alerts: [],
    courses: [],
    submissions: null,
    comments,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
  selectedCourseIds: null,
  ...overrides,
});

function renderComments(syncValue = makeSyncValue()) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={syncValue}>
          <Comments />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

const cardOf = (title) =>
  screen
    .getAllByText(title)
    .map((el) => el.closest('.glass-panel'))
    .find((el) => el != null);

describe('Comments', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.get.mockResolvedValue({ data: mockList });
  });

  it('renders months by default', () => {
    renderComments();
    expect(screen.getByText('2026 Январь')).toBeInTheDocument();
    expect(screen.getByText('2026 Февраль')).toBeInTheDocument();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('renders tab buttons', () => {
    renderComments();
    const tabLabels = screen.getAllByRole('button').map((b) => b.textContent);
    for (const label of ['По месяцам', 'По годам', 'По курсам', 'Не отвеченные', 'Дизлайки']) {
      expect(tabLabels).toContain(label);
    }
  });

  it('shows KPI cards Всего/Студенты/Лайки/Дизлайки', () => {
    renderComments();
    expect(cardOf('Всего комментариев')).not.toBeNull();
    expect(cardOf('Всего комментариев').querySelector('.text-gray-300')).not.toBeNull();
    expect(cardOf('Студенты').querySelector('.text-gray-300')).not.toBeNull();
    expect(cardOf('Лайки').querySelector('.text-neon-green')).not.toBeNull();
    expect(cardOf('Дизлайки').querySelector('.text-crimson-alert')).not.toBeNull();
  });

  it('shows likes green and dislikes red in table cells', () => {
    renderComments();
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0].children[3].style.color).toBe('rgb(74, 222, 128)');
    expect(rows[0].children[4].style.color).toBe('rgb(244, 63, 94)');
  });

  it('switches to years tab on click', async () => {
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('По годам'));
    expect(screen.getByText('Год')).toBeInTheDocument();
    expect(screen.getByText('2026')).toBeInTheDocument();
    expect(screen.getByText('2025')).toBeInTheDocument();
  });

  it('switches to courses tab on click', async () => {
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('По курсам'));
    expect(screen.getByText('Тестовый курс')).toBeInTheDocument();
  });

  it('renders empty state as zeroed KPIs and empty tables (no placeholder)', () => {
    renderComments(
      makeSyncValue({
        months: [],
        years: [],
        by_course: [],
        totals: { comments: 0, students: 0, likes: 0, dislikes: 0, replies: 0 },
      }),
    );
    expect(screen.getByText('Всего комментариев')).toBeInTheDocument();
    expect(screen.getAllByText('Студенты').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Лайки').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Дизлайки').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('shows newest month first by default', () => {
    renderComments();
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Февраль')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Январь')).toBeInTheDocument();
  });

  it('sorts months chronologically by Месяц on header click', async () => {
    const user = userEvent.setup();
    renderComments();
    const header = screen.getByText('Месяц').closest('th');
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Январь')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Февраль')).toBeInTheDocument();
  });

  it('sorts months by Всего numeric', async () => {
    const user = userEvent.setup();
    renderComments();
    const header = screen.getByText('Всего').closest('th');
    await user.click(header);
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Январь')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Февраль')).toBeInTheDocument();
  });

  it('sorts courses alphabetically by default (А-Я)', async () => {
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('По курсам'));
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Алгоритмы')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Тестовый курс')).toBeInTheDocument();
  });

  it('opens course link from course title', async () => {
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('По курсам'));
    const link = screen.getByText('Алгоритмы').closest('a');
    expect(link.getAttribute('href')).toBe('https://stepik.org/course/102');
    expect(link.getAttribute('target')).toBe('_blank');
  });

  it('shows arrow only in the active sort column', async () => {
    const user = userEvent.setup();
    renderComments();
    expect(screen.getByText('Месяц').closest('th').querySelector('span.text-cyber-blue')).not.toBeNull();
    await user.click(screen.getByText('Всего').closest('th'));
    expect(screen.getByText('Всего').closest('th').querySelector('span.text-cyber-blue')).not.toBeNull();
    expect(screen.getByText('Месяц').closest('th').querySelector('span.text-cyber-blue')).toBeNull();
  });

  it('does not fetch the list on aggregate tabs', () => {
    renderComments();
    expect(api.get).not.toHaveBeenCalledWith('/dashboard/comments/list', expect.anything());
  });

  it('fetches unanswered list lazily when tab activated', async () => {
    const user = userEvent.setup();
    renderComments();
    expect(api.get).not.toHaveBeenCalled();
    await user.click(screen.getByText('Не отвеченные'));
    expect(api.get).toHaveBeenCalledWith('/dashboard/comments/list', {
      params: { type: 'unanswered', skip: 0, limit: expect.any(Number), sort: 'time', order: 'desc' },
    });
    expect(await screen.findByText('Вопрос по лекции')).toBeInTheDocument();
    expect(screen.getByText('Иван Петров')).toBeInTheDocument();
  });

  it('passes course_ids to the list endpoint when filter is active', async () => {
    const user = userEvent.setup();
    renderComments(makeSyncValue(mockComments, { selectedCourseIds: ['u1', 'u2'] }));
    await user.click(screen.getByText('Не отвеченные'));
    const call = api.get.mock.calls.find(([url]) => url === '/dashboard/comments/list');
    expect(call[1].params.course_ids).toBe('u1,u2');
  });

  it('opens deep link to comment thread on Шаг', async () => {
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('Не отвеченные'));
    const link = (await screen.findByText('1.1-1')).closest('a');
    expect(link.getAttribute('href')).toBe('https://stepik.org/lesson/10?discussion=101');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('title')).toBe('Модуль 1 — Урок 1');
  });

  it('falls back to comment id when step path is missing', async () => {
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('Не отвеченные'));
    const cell = (await screen.findByText('102')).closest('td');
    expect(cell.querySelector('a')).toBeNull();
    expect(cell.textContent).toBe('102');
  });

  it('shows empty text when list has no comments', async () => {
    api.get.mockResolvedValue({ data: { comments: [], total: 0 } });
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('Не отвеченные'));
    expect(await screen.findByText('Нет комментариев')).toBeInTheDocument();
  });

  it('resets to first page and refetches when filter changes', async () => {
    const user = userEvent.setup();
    const { rerender } = renderComments(makeSyncValue(mockComments, { selectedCourseIds: ['u1'] }));
    await user.click(screen.getByText('Не отвеченные'));
    expect(await screen.findByText('Вопрос по лекции')).toBeInTheDocument();
    rerender(
      <MemoryRouter>
        <AuthProvider>
          <SyncContext.Provider
            value={makeSyncValue(mockComments, { selectedCourseIds: ['u2'] })}
          >
            <Comments />
          </SyncContext.Provider>
        </AuthProvider>
      </MemoryRouter>,
    );
    await screen.findByText('Вопрос по лекции');
    const calls = api.get.mock.calls.filter(([url]) => url === '/dashboard/comments/list');
    expect(calls[calls.length - 1][1].params.course_ids).toBe('u2');
    expect(calls[calls.length - 1][1].params.skip).toBe(0);
  });

  it('shows error banner when list fetch fails', async () => {
    api.get.mockRejectedValue(new Error('Сеть недоступна'));
    const user = userEvent.setup();
    renderComments();
    await user.click(screen.getByText('Не отвеченные'));
    expect(await screen.findByText('Сеть недоступна')).toBeInTheDocument();
  });
});
