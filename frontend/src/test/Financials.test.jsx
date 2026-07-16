import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

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
  recent_payments: [],
}

describe('Financials', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    render(<TestRouter><Financials /></TestRouter>)
    expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
  })

  it('renders page with data', async () => {
    mockGet.mockResolvedValueOnce({ data: mockFinancials })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Финансовая аналитика')).toBeInTheDocument()
    })
    expect(screen.getByText(/Январь 2026/)).toBeInTheDocument()
  })

  it('renders empty state', async () => {
    mockGet.mockResolvedValueOnce({ data: { ...mockFinancials, summary: { ...mockFinancials.summary, total_payments: 0 }, months: [], courses: [], recent_payments: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText(/Финансовые данные пока недоступны/)).toBeInTheDocument()
    })
  })

  it('renders tab buttons when has data', async () => {
    mockGet.mockResolvedValueOnce({ data: mockFinancials })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('По месяцам')).toBeInTheDocument()
    })
    expect(screen.getByText('По курсам')).toBeInTheDocument()
    expect(screen.getByText('Последние операции')).toBeInTheDocument()
  })

  it('renders 5 KPI cards', async () => {
    mockGet.mockResolvedValueOnce({ data: mockFinancials })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getAllByText('Оборот').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Доход').length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText('Возвраты').length).toBeGreaterThanOrEqual(1)
      expect(screen.getByText('Чистый доход')).toBeInTheDocument()
      expect(screen.getAllByText('Покупок').length).toBeGreaterThanOrEqual(1)
    })
  })
})
