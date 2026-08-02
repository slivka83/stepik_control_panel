import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
    net_income: 145000,
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
      net_income: 0,
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
    expect(screen.getByText(/Январь 2026/)).toBeInTheDocument();
  });

  it('renders empty state with zeroed KPI cards and empty tables', () => {
    renderFinancials({
      summary: { total_turnover: 0, total_income: 0, total_refunds: 0, total_payments: 0, net_income: 0 },
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

  it('renders 5 KPI cards', () => {
    renderFinancials();
    expect(screen.getAllByText('Оборот').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Доход').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Возвраты').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Чистый доход')).toBeInTheDocument();
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
    const headers = screen.getAllByRole('columnheader').map((th) => th.textContent);
    expect(headers).toEqual(expect.arrayContaining(['Оплата', 'Доход', 'Подарок', 'UTM']));
    expect(screen.getByText('Иван Петров')).toBeInTheDocument();
    expect(screen.getByText('Подарок')).toBeInTheDocument();
    expect(screen.getByText('Я.Директ')).toBeInTheDocument();
    expect(screen.getByText('Stepik')).toBeInTheDocument();
    expect(screen.getByText('А-ссылка')).toBeInTheDocument();
    expect(screen.getByText('По счету')).toBeInTheDocument();
    expect(screen.getByText('Да')).toBeInTheDocument();
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
});
