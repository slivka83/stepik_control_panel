import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import TestRouter from './TestRouter'
import Cohorts from '../pages/Cohorts'

const makeSyncValue = (cohorts = { active: 0, passive: 0, fading: 0, sleeping: 0 }) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 },
    cohorts,
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials: { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] },
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
})

describe('Cohorts', () => {
  it('renders page title', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 100, passive: 50, fading: 30, sleeping: 20 })}><Cohorts /></TestRouter>)
    expect(screen.getByText('Когортный анализ')).toBeInTheDocument()
  })

  it('renders total student count', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 100, passive: 50, fading: 30, sleeping: 20 })}><Cohorts /></TestRouter>)
    expect(screen.getByText('Всего: 200 студентов')).toBeInTheDocument()
  })

  it('renders all four cohort labels', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 100, passive: 50, fading: 30, sleeping: 20 })}><Cohorts /></TestRouter>)
    expect(screen.getByText('Активные')).toBeInTheDocument()
    expect(screen.getByText('Пассивные')).toBeInTheDocument()
    expect(screen.getByText('Затухающие')).toBeInTheDocument()
    expect(screen.getByText('Спящие')).toBeInTheDocument()
  })

  it('renders cohort values', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 7000, passive: 400, fading: 200, sleeping: 18 })}><Cohorts /></TestRouter>)
    expect(screen.getByText('7000')).toBeInTheDocument()
    expect(screen.getByText('400')).toBeInTheDocument()
    expect(screen.getByText('200')).toBeInTheDocument()
    expect(screen.getByText('18')).toBeInTheDocument()
  })

  it('renders cohort percentages', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 50, passive: 50, fading: 0, sleeping: 0 })}><Cohorts /></TestRouter>)
    expect(screen.getAllByText(/50\.0%/).length).toBeGreaterThanOrEqual(2)
  })

  it('renders day ranges', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 10, passive: 5, fading: 3, sleeping: 2 })}><Cohorts /></TestRouter>)
    expect(screen.getAllByText(/7 дней/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText(/8–30 дней/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText(/30–90 дней/).length).toBeGreaterThanOrEqual(2)
    expect(screen.getAllByText(/90 дней/).length).toBeGreaterThanOrEqual(2)
  })

  it('renders cohort definition section', () => {
    render(<TestRouter syncValue={makeSyncValue()}><Cohorts /></TestRouter>)
    expect(screen.getByText('Определение когорт')).toBeInTheDocument()
    expect(screen.getByText(/Когортный статус определяется/)).toBeInTheDocument()
  })

  it('renders zero state correctly', () => {
    render(<TestRouter syncValue={makeSyncValue()}><Cohorts /></TestRouter>)
    expect(screen.getByText('Всего: 0 студентов')).toBeInTheDocument()
  })
})
