import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import TestRouter from './TestRouter'
import Students from '../pages/Students'

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

describe('Students', () => {
  it('renders all four cohort labels', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 100, passive: 50, fading: 30, sleeping: 20 })}><Students /></TestRouter>)
    expect(screen.getByText('Активные')).toBeInTheDocument()
    expect(screen.getByText('Пассивные')).toBeInTheDocument()
    expect(screen.getByText('Затухающие')).toBeInTheDocument()
    expect(screen.getByText('Спящие')).toBeInTheDocument()
  })

  it('renders cohort percentages', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 50, passive: 50, fading: 0, sleeping: 0 })}><Students /></TestRouter>)
    expect(screen.getAllByText(/%/).length).toBeGreaterThanOrEqual(2)
  })

  it('renders without crashing when no data', () => {
    const { container } = render(<TestRouter syncValue={makeSyncValue()}><Students /></TestRouter>)
    expect(container.querySelector('[class*="flex"]')).toBeInTheDocument()
  })
})
