import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Courses from '../pages/Courses'

const mockKpi = { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 }
const mockCohorts = { active: 0, passive: 0, fading: 0, sleeping: 0 }
const mockRevenue = { months: [] }
const mockAlerts = { alerts: [] }
const mockFinancials = { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] }

const mockAllCourses = (courses) => {
  mockGet
    .mockResolvedValueOnce({ data: mockKpi })
    .mockResolvedValueOnce({ data: mockCohorts })
    .mockResolvedValueOnce({ data: mockRevenue })
    .mockResolvedValueOnce({ data: mockAlerts })
    .mockResolvedValueOnce({ data: { courses } })
    .mockResolvedValueOnce({ data: mockFinancials })
}

describe('Courses', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('renders page title', async () => {
    mockAllCourses([])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Курсы')).toBeInTheDocument()
    })
  })

  it('shows empty state with connect button', async () => {
    mockAllCourses([])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Нет курсов')).toBeInTheDocument()
      expect(screen.getByText('Подключить Stepik')).toBeInTheDocument()
    })
  })

  it('renders course count', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 50 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('1 курсов')).toBeInTheDocument()
    })
  })

  it('renders course title', async () => {
    mockAllCourses([{ id: '1', title: 'Python Course', status: 'Published', health_score: 95, stepik_course_id: 100, enrollment_count: 200 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Python Course')).toBeInTheDocument()
    })
  })

  it('renders enrollment count', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 42 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('42 студентов')).toBeInTheDocument()
    })
  })

  it('renders health score', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Published', health_score: 87.5, stepik_course_id: 100, enrollment_count: 10 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Score: 87.5')).toBeInTheDocument()
    })
  })

  it('renders Published status badge', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 5 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Published')).toBeInTheDocument()
    })
  })

  it('renders Draft status badge', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Draft', health_score: 90, stepik_course_id: 100, enrollment_count: 0 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Draft')).toBeInTheDocument()
    })
  })

  it('renders Stepik deep link', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 12345, enrollment_count: 1 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      const link = screen.getByText('Открыть на Stepik')
      expect(link).toHaveAttribute('href', 'https://stepik.org/course/12345')
      expect(link).toHaveAttribute('target', '_blank')
    })
  })

  it('renders multiple courses', async () => {
    mockAllCourses([
      { id: '1', title: 'Python', status: 'Published', health_score: 95, stepik_course_id: 100, enrollment_count: 200 },
      { id: '2', title: 'JS', status: 'Draft', health_score: 80, stepik_course_id: 200, enrollment_count: 50 },
      { id: '3', title: 'ML', status: 'Published', health_score: 100, stepik_course_id: 300, enrollment_count: 7150 },
    ])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument()
      expect(screen.getByText('JS')).toBeInTheDocument()
      expect(screen.getByText('ML')).toBeInTheDocument()
      expect(screen.getByText('3 курсов')).toBeInTheDocument()
    })
  })

  it('renders zero enrollment count', async () => {
    mockAllCourses([{ id: '1', title: 'C1', status: 'Draft', health_score: 100, stepik_course_id: 100, enrollment_count: 0 }])
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('0 студентов')).toBeInTheDocument()
    })
  })
})
