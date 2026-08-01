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

const makeStudent = (overrides = {}) => ({
  student_id: 123,
  name: 'Иван Петров',
  profile_url: 'https://stepik.org/users/123',
  cohort_status: 'Active',
  courses_count: 1,
  certificates: 0,
  submissions_count: 10,
  submissions_successful: 5,
  comments_count: 2,
  last_activity: '2024-01-15T10:00:00Z',
  ...overrides,
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
    expect(screen.getByText('Нет данных о студентах')).toBeInTheDocument()
  })

  it('does not render list header and total counter', () => {
    render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 }, { students: [], total: 7677 })}><Students /></TestRouter>)
    expect(screen.queryByText('Список студентов')).not.toBeInTheDocument()
    expect(screen.queryByText('7677 всего')).not.toBeInTheDocument()
  })

  it('renders aggregated student rows', () => {
    const studentsData = {
      students: [
        makeStudent({ student_id: 123, name: 'Иван Петров', cohort_status: 'Active', courses_count: 2, certificates: 1, submissions_count: 15, comments_count: 3 }),
        makeStudent({ student_id: 456, name: null, cohort_status: 'Passive', courses_count: 1, certificates: 0, submissions_count: 0, comments_count: 0 }),
      ],
      total: 2,
    }
    render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 1, fading: 0, sleeping: 0 }, studentsData)}><Students /></TestRouter>)
    expect(screen.getByText('Иван Петров')).toBeInTheDocument()
    expect(screen.getByText('Студент 456')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Passive')).toBeInTheDocument()
  })

  it('links student name to profile', () => {
    const studentsData = { students: [makeStudent({ student_id: 777, profile_url: 'https://stepik.org/users/777', name: 'Мария Смирнова' })], total: 1 }
    render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 }, studentsData)}><Students /></TestRouter>)
    const link = screen.getByText('Мария Смирнова').closest('a')
    expect(link).toHaveAttribute('href', 'https://stepik.org/users/777')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders aggregated counters', () => {
    const studentsData = {
      students: [makeStudent({ student_id: 123, courses_count: 3, certificates: 2, submissions_count: 42, submissions_successful: 23, comments_count: 7 })],
      total: 1,
    }
    render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 }, studentsData)}><Students /></TestRouter>)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('42 (55%)')).toBeInTheDocument()
    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('renders zero submissions without percentage', () => {
    const studentsData = {
      students: [makeStudent({ student_id: 123, submissions_count: 0, submissions_successful: 0 })],
      total: 1,
    }
    render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 }, studentsData)}><Students /></TestRouter>)
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText(/\(%/)).not.toBeInTheDocument()
  })

  it('right-aligns activity header and cells', () => {
    const studentsData = { students: [makeStudent()], total: 1 }
    const { container } = render(<TestRouter syncValue={makeSyncValue({ active: 1, passive: 0, fading: 0, sleeping: 0 }, studentsData)}><Students /></TestRouter>)
    const header = screen.getByText('Активность')
    expect(header.className).toContain('text-right')
    const cell = container.querySelector('td.whitespace-nowrap')
    expect(cell.className).toContain('text-right')
  })

  it('renders without crashing when no data', () => {
    const { container } = render(<TestRouter syncValue={makeSyncValue()}><Students /></TestRouter>)
    expect(container.querySelector('[class*="flex"]')).toBeInTheDocument()
  })
})
