import { describe, it, expect, vi } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SyncContext } from '../contexts/SyncContext';
import { AuthProvider } from '../contexts/AuthContext';
import Solutions from '../pages/Solutions';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}));

const mockSubmissions = {
  months: [
    { month: 'Январь 2026', total: 10, correct: 7, students: 6 },
    { month: 'Февраль 2026', total: 20, correct: 15, students: 9 },
  ],
  years: [
    { year: 2026, total: 30, correct: 22, students: 12 },
    { year: 2025, total: 5, correct: 4, students: 3 },
  ],
  by_course: [
    { course_id: 1, stepik_course_id: 101, title: 'Тестовый курс', total: 30, correct: 22, students: 11 },
    { course_id: 2, stepik_course_id: 102, title: 'Алгоритмы', total: 5, correct: 2, students: 2 },
  ],
};

const makeSyncValue = (submissions = mockSubmissions) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {},
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses: [],
    submissions,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
});

function renderSolutions(submissions) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={makeSyncValue(submissions)}>
          <Solutions />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Solutions', () => {
  it('renders months by default', () => {
    renderSolutions();
    expect(screen.getByText('2026 Январь')).toBeInTheDocument();
    expect(screen.getByText('2026 Февраль')).toBeInTheDocument();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
  });

  it('renders tab buttons when has data', () => {
    renderSolutions();
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('По годам')).toBeInTheDocument();
    expect(screen.getByText('По курсам')).toBeInTheDocument();
    expect(screen.getByText('Самые сложные')).toBeInTheDocument();
  });

  it('switches to years tab on click', async () => {
    const user = userEvent.setup();
    renderSolutions();
    await user.click(screen.getByText('По годам'));
    expect(screen.getByText('2026')).toBeInTheDocument();
    expect(screen.getAllByText('30').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('22').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Год')).toBeInTheDocument();
  });

  it('switches to courses tab on click', async () => {
    const user = userEvent.setup();
    renderSolutions();
    await user.click(screen.getByText('По курсам'));
    expect(screen.getByText('Тестовый курс')).toBeInTheDocument();
  });

  it('renders empty state as zeroed KPIs and empty tables (no placeholder)', () => {
    renderSolutions({ months: [], by_course: [], years: [] });
    expect(screen.getByText('Правильных')).toBeInTheDocument();
    expect(screen.getByText('Неправильных')).toBeInTheDocument();
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('По годам')).toBeInTheDocument();
    expect(screen.getByText('Самые сложные')).toBeInTheDocument();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
    expect(screen.queryByText(/Данные о решениях отсутствуют/)).not.toBeInTheDocument();
  });

  it('shows KPI cards Всего решений/Правильных/Неправильных/Успех with column-success color', () => {
    renderSolutions();
    const cardOf = (title) => screen.getByText(title).closest('.glass-panel');
    expect(cardOf('Всего решений')).not.toBeNull();
    expect(cardOf('Правильных').querySelector('.text-gray-300')).not.toBeNull();
    expect(cardOf('Неправильных').querySelector('.text-gray-300')).not.toBeNull();
    expect(screen.getAllByText('Успех')[0].closest('.glass-panel').querySelector('.text-neon-green')).not.toBeNull();
  });

  it('shows newest month first by default', () => {
    renderSolutions();
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Февраль')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Январь')).toBeInTheDocument();
  });

  it('renders students column in months tab and sorts by it', () => {
    renderSolutions();
    const header = screen.getByText('Студенты').closest('th');
    expect(header).not.toBeNull();
    let rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('9')).toBeInTheDocument();
    expect(within(rows[1]).getByText('6')).toBeInTheDocument();
    fireEvent.click(header);
    fireEvent.click(header);
    rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('6')).toBeInTheDocument();
    expect(within(rows[1]).getByText('9')).toBeInTheDocument();
  });

  it('renders students column in years, courses and hardest tabs', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 1, lesson_id: 100, step_number: 2, course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50, weighted_success_pct: 50, students: 8 },
          { stepik_step_id: 2, lesson_id: 200, step_number: 1, course_title: 'Курс Б', total: 5, correct: 1, wrong: 4, success_pct: 20, weighted_success_pct: 20, students: 3 },
        ],
      },
    });
    renderSolutions();
    const cellOf = (row, idx) => row.querySelectorAll('td')[idx].textContent;
    await user.click(screen.getByText('По годам'));
    let rows = screen.getAllByRole('row').slice(1);
    expect(cellOf(rows[0], 1)).toBe('12');
    await user.click(screen.getByText('По курсам'));
    rows = screen.getAllByRole('row').slice(1);
    expect(cellOf(rows[0], 1)).toBe('2');
    expect(cellOf(rows[1], 1)).toBe('11');
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('Курс А');
    rows = screen.getAllByRole('row').slice(1);
    expect(cellOf(rows[0], 2)).toBe('3');
    expect(cellOf(rows[1], 2)).toBe('8');
  });

  it('renders weighted success column only on hardest tab', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 1, lesson_id: 100, step_number: 2, course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50, weighted_success_pct: 40 },
          { stepik_step_id: 2, lesson_id: 200, step_number: 1, course_title: 'Курс Б', total: 5, correct: 1, wrong: 4, success_pct: 20, weighted_success_pct: 30 },
        ],
      },
    });
    renderSolutions({
      months: [{ month: 'Январь 2026', total: 5, correct: 1, success_pct: 3.6, weighted_success_pct: 15.4 }],
      years: [{ year: 2026, total: 5, correct: 1, success_pct: 3.6, weighted_success_pct: 15.4 }],
      by_course: [{ course_id: 1, stepik_course_id: 101, title: 'Тестовый курс', total: 5, correct: 1, success_pct: 3.6, weighted_success_pct: 15.4 }],
    });
    expect(screen.queryByText('Взв. успех')).not.toBeInTheDocument();
    await user.click(screen.getByText('По годам'));
    expect(screen.queryByText('Взв. успех')).not.toBeInTheDocument();
    await user.click(screen.getByText('По курсам'));
    expect(screen.queryByText('Взв. успех')).not.toBeInTheDocument();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('Курс Б');
    expect(screen.getAllByText('Взв. успех').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('30%')).toBeInTheDocument();
    expect(screen.getByText('40%')).toBeInTheDocument();
  });

  it('sorts months chronologically by Месяц on header click', async () => {
    const user = userEvent.setup();
    renderSolutions();
    const header = screen.getByText('Месяц').closest('th');
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Январь')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Февраль')).toBeInTheDocument();
    await user.click(header);
    const rowsDesc = screen.getAllByRole('row').slice(1);
    expect(within(rowsDesc[0]).getByText('2026 Февраль')).toBeInTheDocument();
  });

  it('sorts months by Всего numeric on header click', async () => {
    const user = userEvent.setup();
    renderSolutions();
    const header = screen.getByText('Всего').closest('th');
    await user.click(header);
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Январь')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Февраль')).toBeInTheDocument();
  });

  it('shows arrow only in the active sort column', async () => {
    const user = userEvent.setup();
    renderSolutions();
    expect(screen.getByText('Месяц').closest('th').querySelector('span.text-cyber-blue')).not.toBeNull();
    await user.click(screen.getByText('Всего').closest('th'));
    expect(screen.getByText('Всего').closest('th').querySelector('span.text-cyber-blue')).not.toBeNull();
    expect(screen.getByText('Месяц').closest('th').querySelector('span.text-cyber-blue')).toBeNull();
  });

  it('shows arrow pointing at the anchor values (up on first click, down on second)', async () => {
    const user = userEvent.setup();
    renderSolutions();
    const arrowOf = (th) => th.querySelector('span.text-cyber-blue').textContent;
    expect(arrowOf(screen.getByText('Месяц').closest('th'))).toBe('↑');
    await user.click(screen.getByText('Всего').closest('th'));
    expect(arrowOf(screen.getByText('Всего').closest('th'))).toBe('↑');
    await user.click(screen.getByText('Всего').closest('th'));
    expect(arrowOf(screen.getByText('Всего').closest('th'))).toBe('↓');
    await user.click(screen.getByText('Всего').closest('th'));
    expect(arrowOf(screen.getByText('Всего').closest('th'))).toBe('↑');
  });

  it('sorts text columns alphabetically А-Я on first click', async () => {
    const user = userEvent.setup();
    vi.mocked(api.get).mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 1, lesson_id: 100, step_number: 2, course_title: 'Курс Б', total: 10, correct: 5, wrong: 5, success_pct: 80 },
          { stepik_step_id: 2, lesson_id: 200, step_number: 1, course_title: 'Курс А', total: 5, correct: 1, wrong: 4, success_pct: 20 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('Курс А');
    const header = screen.getByText('Курс').closest('th');
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Курс А')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Курс Б')).toBeInTheDocument();
    expect(header.querySelector('span.text-cyber-blue').textContent).toBe('↑');
    await user.click(header);
    const rowsDesc = screen.getAllByRole('row').slice(1);
    expect(within(rowsDesc[0]).getByText('Курс Б')).toBeInTheDocument();
    expect(header.querySelector('span.text-cyber-blue').textContent).toBe('↓');
  });

  it('sorts years newest first by default and chronologically on click', async () => {
    const user = userEvent.setup();
    renderSolutions();
    await user.click(screen.getByText('По годам'));
    let rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2025')).toBeInTheDocument();
    await user.click(screen.getByText('Год').closest('th'));
    rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2025')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026')).toBeInTheDocument();
  });

  it('sorts years by Всего numeric', async () => {
    const user = userEvent.setup();
    renderSolutions();
    await user.click(screen.getByText('По годам'));
    const header = screen.getByText('Всего').closest('th');
    await user.click(header);
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2025')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026')).toBeInTheDocument();
  });

  it('sorts courses alphabetically by default (А-Я)', async () => {
    renderSolutions();
    const user = userEvent.setup();
    await user.click(screen.getByText('По курсам'));
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Алгоритмы')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Тестовый курс')).toBeInTheDocument();
  });

  it('sorts courses by Всего numeric and has no tooltip on title', async () => {
    const user = userEvent.setup();
    renderSolutions();
    await user.click(screen.getByText('По курсам'));
    const header = screen.getByText('Всего').closest('th');
    await user.click(header);
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Алгоритмы')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Тестовый курс')).toBeInTheDocument();
    expect(rows[0].querySelector('td').getAttribute('title')).toBeNull();
  });

  it('colors success cells red/amber/green by 33/66 thresholds', () => {
    renderSolutions({
      months: [
        { month: 'Январь 2026', total: 10, correct: 3 },
        { month: 'Февраль 2026', total: 10, correct: 5 },
        { month: 'Март 2026', total: 10, correct: 8 },
      ],
      years: [],
      by_course: [],
    });
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0].children[5].style.color).toBe('rgb(74, 222, 128)');
    expect(rows[1].children[5].style.color).toBe('rgb(245, 158, 11)');
    expect(rows[2].children[5].style.color).toBe('rgb(244, 63, 94)');
  });

  it('uses backend success_pct (Wilson) when present', () => {
    renderSolutions({
      months: [
        { month: 'Январь 2026', total: 5, correct: 1, success_pct: 3.6 },
        { month: 'Февраль 2026', total: 1000, correct: 200, success_pct: 17.6 },
      ],
      years: [],
      by_course: [],
    });
    expect(screen.getAllByText('3.6%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('17.6%').length).toBeGreaterThanOrEqual(1);
  });

  it('sorts hardest steps by weighted success default (worst first) and by Всего', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 1, lesson_id: 100, step_number: 2, course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50, weighted_success_pct: 40 },
          { stepik_step_id: 2, lesson_id: 200, step_number: 1, course_title: 'Курс Б', total: 5, correct: 1, wrong: 4, success_pct: 20, weighted_success_pct: 30 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('Курс Б');
    let rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Курс Б')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Курс А')).toBeInTheDocument();
    const header = screen.getByText('Всего').closest('th');
    await user.click(header);
    rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Курс А')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Курс Б')).toBeInTheDocument();
  });

  it('paginates hardest steps', async () => {
    const user = userEvent.setup();
    const steps = Array.from({ length: 20 }, (_, i) => ({
      stepik_step_id: i + 1,
      lesson_id: 100 + i,
      step_number: 1,
      course_title: `Шаг ${i + 1}`,
      total: 10,
      correct: 5,
      wrong: 5,
      success_pct: 50,
    }));
    api.get.mockResolvedValue({ data: { steps } });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('Шаг 1');
    expect(screen.getByText('Страница 1 из 2')).toBeInTheDocument();
    await user.click(screen.getByText('Вперёд →'));
    expect(screen.getByText('Страница 2 из 2')).toBeInTheDocument();
    expect(screen.queryByText('Шаг 1')).not.toBeInTheDocument();
  });

  it('opens step link with lesson and step number', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 42, lesson_id: 7, step_number: 5, module_number: 3, lesson_number: 7, module_title: 'Модуль', lesson_title: 'Урок', course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('3.7-5');
    const link = screen.getByText('3.7-5').closest('a');
    expect(link.getAttribute('href')).toBe('https://stepik.org/lesson/7/step/5');
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('title')).toBe('Модуль — Урок');
  });

  it('shows error instead of empty state when steps load fails', async () => {
    const user = userEvent.setup();
    api.get.mockRejectedValue(new Error('boom'));
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    expect(await screen.findByText('Не удалось загрузить данные')).toBeInTheDocument();
    expect(screen.queryByText('Нет данных')).not.toBeInTheDocument();
  });

  it('opens course link from course title', async () => {
    const user = userEvent.setup();
    renderSolutions();
    await user.click(screen.getByText('По курсам'));
    const link = screen.getByText('Алгоритмы').closest('a');
    expect(link.getAttribute('href')).toBe('https://stepik.org/course/102');
    expect(link.getAttribute('target')).toBe('_blank');
  });

  it('step id cell has text-xs like other cells (row height)', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 42, lesson_id: 7, step_number: 5, course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('42');
    const firstCell = screen.getAllByRole('row')[1].children[0];
    expect(firstCell.className).toContain('text-xs');
  });

  it('shows module.lesson-step path when module/lesson numbers present', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 42, lesson_id: 7, step_number: 2, module_number: 3, lesson_number: 7, course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    expect(await screen.findByText('3.7-2')).toBeInTheDocument();
    expect(screen.queryByText('42')).not.toBeInTheDocument();
  });

  it('falls back to step id when module/lesson numbers missing', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 42, lesson_id: 7, step_number: 5, course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    expect(await screen.findByText('42')).toBeInTheDocument();
    expect(screen.queryByText('7-5')).not.toBeInTheDocument();
  });

  it('shows module name — lesson name in step tooltip when titles present', async () => {
    const user = userEvent.setup();
    api.get.mockResolvedValue({
      data: {
        steps: [
          { stepik_step_id: 42, lesson_id: 7, step_number: 2, module_number: 3, lesson_number: 7, module_title: 'Деревья решений', lesson_title: 'Регрессия', course_title: 'Курс А', total: 10, correct: 5, wrong: 5, success_pct: 50 },
        ],
      },
    });
    renderSolutions();
    await user.click(screen.getByText('Самые сложные'));
    await screen.findByText('3.7-2');
    const link = screen.getByText('3.7-2').closest('a');
    expect(link.getAttribute('title')).toBe('Деревья решений — Регрессия');
  });
});
