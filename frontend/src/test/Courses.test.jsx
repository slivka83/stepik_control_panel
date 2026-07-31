import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import TestRouter from './TestRouter'
import Courses from '../pages/Courses'

const defaultCourse = {
  id: '1', title: 'C1', status: 'Published',
  stepik_course_id: 100, enrollment_count: 50,
  submissions_total: 100, submissions_correct: 80,
  comments_count: 30, reviews_count: 10, average_rating: 4.5,
}

const makeSyncValue = (courses = []) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: courses.length, courses_published: courses.filter(c => c.status === 'Published').length, courses_unpublished: courses.filter(c => c.status !== 'Published').length, net_income: 0, total_turnover: 0, total_payments: 0, total_refunds: 0, total_income: 0, total_comments: 0, average_rating: 0 },
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
  it('renders KPI cards', () => {
    render(<TestRouter syncValue={makeSyncValue([defaultCourse])}><Courses /></TestRouter>)
    expect(screen.getByText('Всего курсов')).toBeInTheDocument()
    expect(screen.getByText('Опубликовано')).toBeInTheDocument()
    expect(screen.getByText('Черновиков')).toBeInTheDocument()
  })

  it('shows empty state with connect button', () => {
    render(<TestRouter syncValue={makeSyncValue()}><Courses /></TestRouter>)
    expect(screen.getByText('Нет курсов')).toBeInTheDocument()
    expect(screen.getByText('Подключить Stepik')).toBeInTheDocument()
  })

  it('renders course title in table', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, title: 'Python Course' }])}><Courses /></TestRouter>)
    expect(screen.getByText('Python Course')).toBeInTheDocument()
  })

  it('renders enrollment count', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, enrollment_count: 42 }])}><Courses /></TestRouter>)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders comments count', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, comments_count: 15 }])}><Courses /></TestRouter>)
    expect(screen.getByText('15')).toBeInTheDocument()
  })

  it('renders submissions with percentage', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, submissions_total: 200, submissions_correct: 150 }])}><Courses /></TestRouter>)
    expect(screen.getByText('200 (75%)')).toBeInTheDocument()
  })

  it('renders Опубликован status', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, status: 'Published' }])}><Courses /></TestRouter>)
    expect(screen.getAllByText('Опубликован').length).toBeGreaterThanOrEqual(1)
  })

  it('renders Черновик status', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, status: 'Draft' }])}><Courses /></TestRouter>)
    expect(screen.getByText('Черновик')).toBeInTheDocument()
  })

  it('renders Stepik deep link', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, stepik_course_id: 12345 }])}><Courses /></TestRouter>)
    const link = screen.getByText('C1').closest('a')
    expect(link).toHaveAttribute('href', 'https://stepik.org/course/12345')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders multiple courses', () => {
    render(<TestRouter syncValue={makeSyncValue([
      { ...defaultCourse, id: '1', title: 'Python' },
      { ...defaultCourse, id: '2', title: 'JS' },
      { ...defaultCourse, id: '3', title: 'ML' },
    ])}><Courses /></TestRouter>)
    expect(screen.getByText('Python')).toBeInTheDocument()
    expect(screen.getByText('JS')).toBeInTheDocument()
    expect(screen.getByText('ML')).toBeInTheDocument()
  })

  it('renders table headers', () => {
    render(<TestRouter syncValue={makeSyncValue([defaultCourse])}><Courses /></TestRouter>)
    expect(screen.getByText('Название')).toBeInTheDocument()
    expect(screen.getByText('Статус')).toBeInTheDocument()
    expect(screen.getByText('Стоимость')).toBeInTheDocument()
    expect(screen.getAllByText('Опубликован').length).toBeGreaterThanOrEqual(1)
  })

  it('renders price', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, price: 2990 }])}><Courses /></TestRouter>)
    expect(screen.getByText(/990/)).toBeInTheDocument()
  })

  it('renders price as dash when null', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, price: null }])}><Courses /></TestRouter>)
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThanOrEqual(1)
  })

  it('renders published_at date', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, published_at: '2024-06-15T10:00:00Z' }])}><Courses /></TestRouter>)
    expect(screen.getByText(/2024/)).toBeInTheDocument()
  })

  it('renders rating with color', () => {
    render(<TestRouter syncValue={makeSyncValue([{ ...defaultCourse, average_rating: 4.5 }])}><Courses /></TestRouter>)
    expect(screen.getByText('4.50')).toBeInTheDocument()
  })

  it('sorts by Студенты on header click', () => {
    render(<TestRouter syncValue={makeSyncValue([
      { ...defaultCourse, id: '1', title: 'Low', enrollment_count: 5 },
      { ...defaultCourse, id: '2', title: 'High', enrollment_count: 500 },
      { ...defaultCourse, id: '3', title: 'Mid', enrollment_count: 50 },
    ])}><Courses /></TestRouter>)

    const header = screen.getByText('Студенты').closest('th')
    fireEvent.click(header)
    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('High')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Low')).toBeInTheDocument()

    fireEvent.click(header)
    const rowsAsc = screen.getAllByRole('row').slice(1)
    expect(within(rowsAsc[0]).getByText('Low')).toBeInTheDocument()
    expect(within(rowsAsc[2]).getByText('High')).toBeInTheDocument()
  })

  it('keeps drafts last when sorting by Опубликован desc', () => {
    render(<TestRouter syncValue={makeSyncValue([
      { ...defaultCourse, id: '1', title: 'Draft', published_at: null },
      { ...defaultCourse, id: '2', title: 'Old', published_at: '2024-01-01T00:00:00Z' },
      { ...defaultCourse, id: '3', title: 'New', published_at: '2026-07-01T00:00:00Z' },
    ])}><Courses /></TestRouter>)

    const rows = screen.getAllByRole('row').slice(1)
    expect(within(rows[0]).getByText('New')).toBeInTheDocument()
    expect(within(rows[1]).getByText('Old')).toBeInTheDocument()
    expect(within(rows[2]).getByText('Draft')).toBeInTheDocument()
  })
})
