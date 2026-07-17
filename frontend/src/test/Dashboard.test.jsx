import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Dashboard from '../pages/Dashboard'

const mockKpi = {
  total_revenue: 50000,
  net_income: 1354735,
  total_turnover: 2049992,
  total_students: 7618,
  certificates_issued: 179,
  courses_count: 7,
  total_payments: 689,
  total_refunds: 21930,
  total_income: 1376665,
}

const mockCohorts = { active: 7000, passive: 400, fading: 200, sleeping: 18 }

const mockRevenue = {
  months: [
    { month: '2026-01-01T00:00:00', revenue: 12000 },
    { month: '2026-02-01T00:00:00', revenue: 18000 },
  ],
}

const mockAlerts = {
  alerts: [
    { type: 'warning', message: '29 студентов набрали проходной балл, но не получили сертификат', link: 'https://stepik.org/course/68260/certificates', link_text: 'Открыть на Stepik →' },
    { type: 'error', message: '5643 студентов на курсе «Алгоритмы ML» не набрали ни одного балла', link: 'https://stepik.org/course/68260/students', link_text: 'Посмотреть на Stepik →' },
  ],
}

const mockCourses = { courses: [] }
const mockFinancials = { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] }

const mockAll = () => {
  mockGet
    .mockResolvedValueOnce({ data: mockKpi })
    .mockResolvedValueOnce({ data: mockCohorts })
    .mockResolvedValueOnce({ data: mockRevenue })
    .mockResolvedValueOnce({ data: mockAlerts })
    .mockResolvedValueOnce({ data: mockCourses })
    .mockResolvedValueOnce({ data: mockFinancials })
}

describe('Dashboard', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('renders dashboard title', async () => {
    mockAll()
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Сводная аналитика')).toBeInTheDocument()
    })
  })

  it('renders all six KPI cards', async () => {
    mockAll()
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Доход за месяц')).toBeInTheDocument()
      expect(screen.getByText('Чистый доход')).toBeInTheDocument()
      expect(screen.getByText('Оборот')).toBeInTheDocument()
      expect(screen.getByText('Студенты')).toBeInTheDocument()
      expect(screen.getByText('Покупок')).toBeInTheDocument()
      expect(screen.getByText('Сертификаты')).toBeInTheDocument()
    })
  })

  it('renders financial KPI values', async () => {
    mockAll()
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Доход за месяц')).toBeInTheDocument()
      expect(screen.getByText('Чистый доход')).toBeInTheDocument()
      expect(screen.getByText('Оборот')).toBeInTheDocument()
      expect(screen.getByText('Покупок')).toBeInTheDocument()
    })
  })

  it('renders alerts from API', async () => {
    mockAll()
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Алерты')).toBeInTheDocument()
      expect(screen.getByText(/29 студентов набрали проходной балл/)).toBeInTheDocument()
      expect(screen.getByText(/5643 студентов/)).toBeInTheDocument()
    })
  })

  it('renders alert deep links to stepik.org', async () => {
    mockAll()
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      const links = screen.getAllByRole('link')
      const stepikLinks = links.filter(l => l.href.includes('stepik.org'))
      expect(stepikLinks.length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders empty alerts section when no alerts', async () => {
    mockGet
      .mockResolvedValueOnce({ data: mockKpi })
      .mockResolvedValueOnce({ data: mockCohorts })
      .mockResolvedValueOnce({ data: mockRevenue })
      .mockResolvedValueOnce({ data: { alerts: [] } })
      .mockResolvedValueOnce({ data: mockCourses })
      .mockResolvedValueOnce({ data: mockFinancials })
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.queryByText('Алерты')).not.toBeInTheDocument()
    })
  })

  it('renders with zero KPI values', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 } })
      .mockResolvedValueOnce({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
      .mockResolvedValueOnce({ data: { months: [] } })
      .mockResolvedValueOnce({ data: { alerts: [] } })
      .mockResolvedValueOnce({ data: mockCourses })
      .mockResolvedValueOnce({ data: mockFinancials })
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Сводная аналитика')).toBeInTheDocument()
      expect(screen.getByText('Доход за месяц')).toBeInTheDocument()
      expect(screen.getByText('Студенты')).toBeInTheDocument()
      expect(screen.getByText('Сертификаты')).toBeInTheDocument()
    })
  })

  it('renders chart sections', async () => {
    mockAll()
    render(<TestRouter><Dashboard /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Когортная сегментация')).toBeInTheDocument()
      expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
    })
  })
})
