import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import TestRouter from './TestRouter'
import Students from '../pages/Students'

const makeSyncValue = (cohorts = { active: 0, passive: 0, fading: 0, sleeping: 0 }, studentsData = { students: [], total: 0 }) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 },
    cohorts,
    revenue: { months: [] },
    alerts: [],
    courses: [],
    financials: { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] },
    students: studentsData,
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

  it('renders student table with no data message', () => {
    render(<TestRouter syncValue={makeSyncValue()}><Students /></TestRouter>)
    expect(screen.getByText('Список студентов')).toBeInTheDocument()
    expect(screen.getByText('Нет данных о студентах')).toBeInTheDocument()
  })

  it('renders student rows', () => {
    const studentsData = {
      students: [
        { student_id: 123, course_id: 'uuid-1', course_title: 'Test Course', cohort_status: 'Active', points_earned: 50, certificate_issued: false, last_viewed_at: '2024-01-15T10:00:00Z', date_joined: '2024-01-01T10:00:00Z' },
        { student_id: 456, course_id: 'uuid-2', course_title: 'Python 101', cohort_status: 'Passive', points_earned: 100, certificate_issued: true, last_viewed_at: '2024-06-01T10:00:00Z', date_joined: '2024-03-01T10:00:00Z' },
      ],
      total: 2,
    }
    render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 1, fading: 0, sleeping: 0 }, studentsData)}><Students /></TestRouter>)
    expect(screen.getByText('123')).toBeInTheDocument()
    expect(screen.getByText('456')).toBeInTheDocument()
    expect(screen.getByText('Test Course')).toBeInTheDocument()
    expect(screen.getByText('Python 101')).toBeInTheDocument()
    expect(screen.getByText('Да')).toBeInTheDocument()
    expect(screen.getAllByText('Active').length).toBeGreaterThanOrEqual(1)
  })

  it('renders without crashing when no data', () => {
    const { container } = render(<TestRouter syncValue={makeSyncValue()}><Students /></TestRouter>)
    expect(container.querySelector('[class*="flex"]')).toBeInTheDocument()
  })
})
