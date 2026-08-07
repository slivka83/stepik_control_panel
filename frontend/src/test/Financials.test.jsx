import { describe, it, expect, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { SyncContext } from '../contexts/SyncContext';
import { AuthProvider } from '../contexts/AuthContext';
import Financials from '../pages/Financials';

const mockFinancials = {
  summary: {
    total_turnover: 200000,
    total_income: 150000,
    total_refunds: 5000,
    total_payments: 42,
  },
  months: [
    {
      month: 'Январь 2026',
      year: 2026,
      month_num: 1,
      turnover: 70000,
      income: 50000,
      refunds: 0,
      payments_count: 15,
      refunds_count: 0,
    },
  ],
  years: [{ year: 2026, turnover: 70000, income: 50000, refunds: 0, payments_count: 15 }],
  days: [
    { day: '2026-01-15', payments_count: 1, turnover: 7000, income: 5000, refunds: 0, refunds_count: 0 },
    { day: '2026-01-14', payments_count: 1, turnover: 7000, income: 0, refunds: 500, refunds_count: 1 },
    { day: '2026-01-13', payments_count: 1, turnover: 4000, income: 3000, refunds: 0, refunds_count: 0 },
  ],
  courses: [{ course_id: 68260, title: 'Тестовый курс', turnover: 70000, income: 50000, refunds: 0, payments: 15 }],
  promos: [
    {
      promo_code: 'DISCOUNT10',
      payments: 1,
      turnover: 5000,
      income: 4000,
      refunds: 0,
      last_used: '2026-01-15T10:00:00',
    },
  ],
  utms: [
    { utm_source: 'Я.Директ', payments: 1, turnover: 7000, income: 5000, refunds: 0, last_used: '2026-01-15T10:00:00' },
  ],
  recent_payments: [
    {
      id: 'p1',
      course: 'Тестовый курс',
      amount: 5000,
      payment_amount: 7000,
      status: 'debited',
      time: '2026-01-15T10:00:00',
      promo_code: 'WELCOME',
      channel: 'Stepik',
      is_gift: false,
      student: 'Иван Петров',
      buyer: 777,
      utm_source: 'yandex_stpk',
      utm_source_label: 'Я.Директ',
      raw: {
        id: 1,
        time: '2026-01-15T10:00:00',
        course: 68260,
        amount: 5000,
        status: 'debited',
        last_course_click_utm: { utm_source: 'yandex_stpk', utm_medium: 'cpc' },
      },
    },
    {
      id: 'p2',
      course: 'Второй курс',
      amount: -500,
      payment_amount: 7000,
      status: 'refunded',
      time: '2026-01-14T09:30:00',
      promo_code: null,
      channel: 'А-ссылка',
      is_gift: false,
      student: 'Петр Иванов',
    },
    {
      id: 'p3',
      course: 'Третий курс',
      amount: 3000,
      payment_amount: 4000,
      status: 'debited',
      time: '2026-01-13T08:00:00',
      promo_code: null,
      channel: 'По счету',
      is_gift: true,
      student: null,
    },
  ],
};

const makeSyncValue = (financials = mockFinancials) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {
      total_revenue: 0,
      total_students: 0,
      certificates_issued: 0,
      courses_count: 0,
      total_turnover: 0,
      total_payments: 0,
      total_refunds: 0,
      total_income: 0,
    },
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
});

function renderFinancials(financials) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={makeSyncValue(financials)}>
          <Financials />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Financials', () => {
  it('renders page with data', () => {
    renderFinancials();
    expect(screen.getByText('Месяц')).toBeInTheDocument();
    expect(screen.getByText('2026 Январь')).toBeInTheDocument();
  });

  it('renders empty state with zeroed KPI cards and empty tables', () => {
    renderFinancials({
      summary: { total_turnover: 0, total_income: 0, total_refunds: 0, total_payments: 0 },
      months: [],
      courses: [],
      recent_payments: [],
    });
    expect(screen.getAllByText('Оборот').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('Последние операции')).toBeInTheDocument();
    expect(screen.queryByText(/Финансовые данные пока недоступны/)).not.toBeInTheDocument();
  });

  it('renders tab buttons when has data', () => {
    renderFinancials();
    expect(screen.getByText('По месяцам')).toBeInTheDocument();
    expect(screen.getByText('По годам')).toBeInTheDocument();
    expect(screen.getByText('По дням')).toBeInTheDocument();
    expect(screen.getByText('По курсам')).toBeInTheDocument();
    expect(screen.getByText('Последние операции')).toBeInTheDocument();
  });

  it('switches to years tab on click', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('По годам'));
    expect(screen.getByText('2026')).toBeInTheDocument();
    expect(screen.getAllByText('Покупок').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  it('switches to days tab on click', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('По дням'));
    expect(screen.getByText('Дата')).toBeInTheDocument();
    expect(screen.getByText('15.01.2026')).toBeInTheDocument();
    expect(screen.getByText('14.01.2026')).toBeInTheDocument();
    expect(screen.getByText('5 000 ₽')).toBeInTheDocument();
    expect(screen.getByText('-500 ₽')).toHaveClass('text-crimson-alert');
  });

  it('renders 4 KPI cards', () => {
    renderFinancials();
    expect(screen.getAllByText('Оборот').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Доход').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Возвраты').length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText('Чистый доход')).not.toBeInTheDocument();
    expect(screen.getAllByText('Покупок').length).toBeGreaterThanOrEqual(1);
  });

  it('switches to courses tab on click', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('По курсам'));
    expect(screen.getByText('Тестовый курс')).toBeInTheDocument();
    expect(screen.getByText('Стоимость')).toBeInTheDocument();
  });

  it('switches to recent payments tab on click', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('Последние операции'));
    expect(screen.getByText('WELCOME')).toBeInTheDocument();
    expect(screen.getByText('Тестовый курс')).toBeInTheDocument();
    expect(screen.getByText('UTM')).toBeInTheDocument();
    expect(screen.getByText('Канал')).toBeInTheDocument();
    expect(screen.getByText('Студент')).toBeInTheDocument();
    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent.replace(/[↑↓]/g, ''));
    expect(headers).toEqual(expect.arrayContaining(['Оплата', 'Комиссия', 'Доход', 'Подарок', 'UTM']));
    expect(screen.getByText('Иван Петров')).toBeInTheDocument();
    expect(screen.getByText('Подарок')).toBeInTheDocument();
    expect(screen.getByText('Я.Директ')).toBeInTheDocument();
    expect(screen.getByText('Stepik')).toBeInTheDocument();
    expect(screen.getByText('А-ссылка')).toBeInTheDocument();
    expect(screen.getByText('По счету')).toBeInTheDocument();
    expect(screen.getByText('Да')).toBeInTheDocument();
    expect(screen.getByText('29%')).toBeInTheDocument();
    expect(screen.getByText('93%')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByTitle('2 000 ₽')).toBeInTheDocument();
    expect(screen.getByTitle('6 500 ₽')).toBeInTheDocument();
    const tooltip = screen.getByTitle(/utm_source: yandex_stpk/);
    expect(tooltip).toHaveAttribute('title', expect.stringContaining('utm_medium: cpc'));
    expect(tooltip.getAttribute('title')).not.toContain('amount');
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
  });

  it('switches to utm tab on click', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('По UTM'));
    expect(screen.getByText('Я.Директ')).toBeInTheDocument();
    expect(screen.getByText('Последнее применение')).toBeInTheDocument();
    expect(screen.getByText('7 000 ₽')).toBeInTheDocument();
  });

  it('renders refunded amount in red with line-through', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('Последние операции'));
    expect(screen.getByText('-500 ₽')).toHaveClass('line-through', 'text-crimson-alert');
    expect(screen.queryByText('Возврат')).not.toBeInTheDocument();
  });

  it('sorts months chronologically on Месяц header click', async () => {
    const user = userEvent.setup();
    renderFinancials({
      summary: mockFinancials.summary,
      months: [
        { month: 'Январь 2025', year: 2025, month_num: 1, turnover: 10, income: 5, refunds: 0, payments_count: 1 },
        { month: 'Март 2026', year: 2026, month_num: 3, turnover: 30, income: 15, refunds: 0, payments_count: 3 },
        { month: 'Февраль 2026', year: 2026, month_num: 2, turnover: 20, income: 10, refunds: 0, payments_count: 2 },
      ],
      years: [],
      courses: [],
      recent_payments: [],
    });
    let rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Март')).toBeInTheDocument();
    await user.click(screen.getByText('Месяц').closest('th'));
    rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2025 Январь')).toBeInTheDocument();
    expect(within(rows[1]).getByText('2026 Февраль')).toBeInTheDocument();
    expect(within(rows[2]).getByText('2026 Март')).toBeInTheDocument();
  });

  it('sorts months by Оборот numeric on header click', async () => {
    const user = userEvent.setup();
    renderFinancials({
      summary: mockFinancials.summary,
      months: [
        {
          month: 'Январь 2026',
          year: 2026,
          month_num: 1,
          turnover: 70000,
          income: 50000,
          refunds: 0,
          payments_count: 15,
        },
        {
          month: 'Февраль 2026',
          year: 2026,
          month_num: 2,
          turnover: 90000,
          income: 60000,
          refunds: 0,
          payments_count: 20,
        },
      ],
      years: [],
      courses: [],
      recent_payments: [],
    });
    const header = screen.getAllByRole('columnheader').find((th) => th.textContent.replace(/[↑↓]/g, '') === 'Оборот');
    await user.click(header);
    let rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Февраль')).toBeInTheDocument();
    await user.click(header);
    rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('2026 Январь')).toBeInTheDocument();
  });

  it('links student to Stepik profile in recent payments', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('Последние операции'));
    const link = screen.getByText('Иван Петров').closest('a');
    expect(link).toHaveAttribute('href', 'https://stepik.org/users/777');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('links course to Stepik in По курсам tab', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('По курсам'));
    const link = screen.getByText('Тестовый курс').closest('a');
    expect(link).toHaveAttribute('href', 'https://stepik.org/course/68260');
    expect(link).toHaveAttribute('target', '_blank');
  });

  it('keeps null students last when sorting recent by Студент', async () => {
    const user = userEvent.setup();
    renderFinancials();
    await user.click(screen.getByText('Последние операции'));
    await user.click(screen.getByText('Студент').closest('th'));
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows[0].children[2].textContent).toBe('Иван Петров');
    expect(rows[2].children[2].textContent).toBe('—');
  });

  it('keeps null price last when sorting courses by Стоимость', async () => {
    const user = userEvent.setup();
    renderFinancials({
      summary: mockFinancials.summary,
      months: mockFinancials.months,
      years: mockFinancials.years,
      courses: [
        { course_id: 1, title: 'Без цены', turnover: 0, income: 0, refunds: 0, payments: 0, price: null },
        { course_id: 2, title: 'Дешёвый', turnover: 0, income: 0, refunds: 0, payments: 0, price: 1000 },
      ],
      recent_payments: [],
    });
    await user.click(screen.getByText('По курсам'));
    const header = screen.getByText('Стоимость').closest('th');
    await user.click(header);
    await user.click(header);
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[1]).getByText('Без цены')).toBeInTheDocument();
  });

  it('shows arrow pointing at the anchor values (up on first click, down on second)', async () => {
    const user = userEvent.setup();
    renderFinancials();
    const thOf = (label) =>
      screen.getAllByRole('columnheader').find((th) => th.textContent.replace(/[↑↓]/g, '') === label);
    const arrowOf = (th) => th.querySelector('span.text-cyber-blue').textContent;
    expect(arrowOf(thOf('Месяц'))).toBe('↑');
    const header = thOf('Оборот');
    await user.click(header);
    expect(arrowOf(header)).toBe('↑');
    await user.click(header);
    expect(arrowOf(header)).toBe('↓');
  });
});
