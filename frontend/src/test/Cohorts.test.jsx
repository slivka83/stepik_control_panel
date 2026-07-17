import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Cohorts from '../pages/Cohorts'

const mockKpi = { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 }
const mockRevenue = { months: [] }
const mockAlerts = { alerts: [] }
const mockCourses = { courses: [] }
const mockFinancials = { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] }

const mockAllCohorts = (cohorts) => {
  mockGet
    .mockResolvedValueOnce({ data: mockKpi })
    .mockResolvedValueOnce({ data: cohorts })
    .mockResolvedValueOnce({ data: mockRevenue })
    .mockResolvedValueOnce({ data: mockAlerts })
    .mockResolvedValueOnce({ data: mockCourses })
    .mockResolvedValueOnce({ data: mockFinancials })
}

describe('Cohorts', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('renders page title', async () => {
    mockAllCohorts({ active: 100, passive: 50, fading: 30, sleeping: 20 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Когортный анализ')).toBeInTheDocument()
    })
  })

  it('renders total student count', async () => {
    mockAllCohorts({ active: 100, passive: 50, fading: 30, sleeping: 20 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Всего: 200 студентов')).toBeInTheDocument()
    })
  })

  it('renders all four cohort labels', async () => {
    mockAllCohorts({ active: 100, passive: 50, fading: 30, sleeping: 20 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Активные')).toBeInTheDocument()
      expect(screen.getByText('Пассивные')).toBeInTheDocument()
      expect(screen.getByText('Затухающие')).toBeInTheDocument()
      expect(screen.getByText('Спящие')).toBeInTheDocument()
    })
  })

  it('renders cohort values', async () => {
    mockAllCohorts({ active: 7000, passive: 400, fading: 200, sleeping: 18 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('7000')).toBeInTheDocument()
      expect(screen.getByText('400')).toBeInTheDocument()
      expect(screen.getByText('200')).toBeInTheDocument()
      expect(screen.getByText('18')).toBeInTheDocument()
    })
  })

  it('renders cohort percentages', async () => {
    mockAllCohorts({ active: 50, passive: 50, fading: 0, sleeping: 0 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getAllByText(/50\.0%/).length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders day ranges', async () => {
    mockAllCohorts({ active: 10, passive: 5, fading: 3, sleeping: 2 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getAllByText(/7 дней/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/8–30 дней/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/30–90 дней/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/90 дней/).length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders cohort definition section', async () => {
    mockAllCohorts({ active: 0, passive: 0, fading: 0, sleeping: 0 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Определение когорт')).toBeInTheDocument()
      expect(screen.getByText(/Когортный статус определяется/)).toBeInTheDocument()
    })
  })

  it('renders zero state correctly', async () => {
    mockAllCohorts({ active: 0, passive: 0, fading: 0, sleeping: 0 })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Всего: 0 студентов')).toBeInTheDocument()
    })
  })
})
