import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import TestRouter from './TestRouter'
import Courses from '../pages/Courses'

const makeSyncValue = (courses = []) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0 },
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses,
    financials: { summary: { total_payments: 0 }, months: [], courses: [], recent_payments: [] },
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
})

describe('Courses', () => {
  it('renders page title', () => {
    render(<TestRouter syncValue={makeSyncValue()}><Courses /></TestRouter>)
    expect(screen.getByText('Курсы')).toBeInTheDocument()
  })

  it('shows empty state with connect button', () => {
    render(<TestRouter syncValue={makeSyncValue()}><Courses /></TestRouter>)
    expect(screen.getByText('Нет курсов')).toBeInTheDocument()
    expect(screen.getByText('Подключить Stepik')).toBeInTheDocument()
  })

  it('renders course count', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 50 }])}><Courses /></TestRouter>)
    expect(screen.getByText('1 курс')).toBeInTheDocument()
  })

  it('renders course title', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'Python Course', status: 'Published', health_score: 95, stepik_course_id: 100, enrollment_count: 200 }])}><Courses /></TestRouter>)
    expect(screen.getByText('Python Course')).toBeInTheDocument()
  })

  it('renders enrollment count', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 42 }])}><Courses /></TestRouter>)
    expect(screen.getByText('42 студента')).toBeInTheDocument()
  })

  it('renders health score', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Published', health_score: 87.5, stepik_course_id: 100, enrollment_count: 10 }])}><Courses /></TestRouter>)
    expect(screen.getByText('Score: 87.5')).toBeInTheDocument()
  })

  it('renders Published status badge', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 5 }])}><Courses /></TestRouter>)
    expect(screen.getByText('Published')).toBeInTheDocument()
  })

  it('renders Draft status badge', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Draft', health_score: 90, stepik_course_id: 100, enrollment_count: 0 }])}><Courses /></TestRouter>)
    expect(screen.getByText('Draft')).toBeInTheDocument()
  })

  it('renders Stepik deep link', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 12345, enrollment_count: 1 }])}><Courses /></TestRouter>)
    const link = screen.getByText('Открыть на Stepik')
    expect(link).toHaveAttribute('href', 'https://stepik.org/course/12345')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders multiple courses', () => {
    render(<TestRouter syncValue={makeSyncValue([
      { id: '1', title: 'Python', status: 'Published', health_score: 95, stepik_course_id: 100, enrollment_count: 200 },
      { id: '2', title: 'JS', status: 'Draft', health_score: 80, stepik_course_id: 200, enrollment_count: 50 },
      { id: '3', title: 'ML', status: 'Published', health_score: 100, stepik_course_id: 300, enrollment_count: 7150 },
    ])}><Courses /></TestRouter>)
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('JS')).toBeInTheDocument()
    expect(screen.getByText('ML')).toBeInTheDocument()
      expect(screen.getByText('3 курса')).toBeInTheDocument()
  })

  it('renders zero enrollment count', () => {
    render(<TestRouter syncValue={makeSyncValue([{ id: '1', title: 'C1', status: 'Draft', health_score: 100, stepik_course_id: 100, enrollment_count: 0 }])}><Courses /></TestRouter>)
    expect(screen.getByText('0 студентов')).toBeInTheDocument()
  })
})
