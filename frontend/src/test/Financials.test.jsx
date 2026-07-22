import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { SyncContext } from '../contexts/SyncContext'
import { AuthProvider } from '../contexts/AuthContext'
import Financials from '../pages/Financials'

const mockFinancials = {
  summary: {
    total_turnover: 200000,
    total_income: 150000,
    total_refunds: 5000,
    total_payments: 42,
    net_income: 145000,
  },
  months: [
    { month: 'Январь 2026', year: 2026, month_num: 1, turnover: 70000, income: 50000, refunds: 0, payments_count: 15, refunds_count: 0 },
  ],
  courses: [
    { course_id: 68260, title: 'Тестовый курс', turnover: 70000, income: 50000, refunds: 0, payments: 15 },
  ],
  recent_payments: [
    { id: 'p1', course: 'Тестовый курс', amount: 5000, payment_amount: 7000, status: 'debited', time: '2026-01-15T10:00:00', promo_code: 'WELCOME' },
  ],
}

const makeSyncValue = (financials = mockFinancials) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 },
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
})

function renderFinancials(financials) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={makeSyncValue(financials)}>
          <Financials />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('Financials', () => {
  it('renders page with data', () => {
    renderFinancials()
    expect(screen.getByText('Финансовая аналитика')).toBeInTheDocument()
    expect(screen.getByText(/Январь 2026/)).toBeInTheDocument()
  })

  it('renders empty state', () => {
    renderFinancials({ summary: { total_turnover: 0, total_income: 0, total_refunds: 0, total_payments: 0, net_income: 0 }, months: [], courses: [], recent_payments: [] })
    expect(screen.getByText(/Финансовые данные пока недоступны/)).toBeInTheDocument()
  })

  it('renders tab buttons when has data', () => {
    renderFinancials()
    expect(screen.getByText('По месяцам')).toBeInTheDocument()
    expect(screen.getByText('По курсам')).toBeInTheDocument()
    expect(screen.getByText('Последние операции')).toBeInTheDocument()
  })

  it('renders 5 KPI cards', () => {
    renderFinancials()
    expect(screen.getAllByText('Оборот').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Доход').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('Возвраты').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Чистый доход')).toBeInTheDocument()
    expect(screen.getAllByText('Покупок').length).toBeGreaterThanOrEqual(1)
  })

  it('switches to courses tab on click', async () => {
    const user = userEvent.setup()
    renderFinancials()
    await user.click(screen.getByText('По курсам'))
    expect(screen.getByText('Доход по курсам')).toBeInTheDocument()
  })

  it('switches to recent payments tab on click', async () => {
    const user = userEvent.setup()
    renderFinancials()
    await user.click(screen.getByText('Последние операции'))
    expect(screen.getByText('Последние операции (1 операция)')).toBeInTheDocument()
  })
})
