import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Courses from '../pages/Courses'

describe('Courses', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    render(<TestRouter><Courses /></TestRouter>)
    expect(screen.getByText('Загрузка курсов...')).toBeInTheDocument()
  })

  it('renders page title', async () => {
    mockGet.mockResolvedValue({ data: { courses: [] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Курсы')).toBeInTheDocument()
    })
  })

  it('shows empty state with connect button', async () => {
    mockGet.mockResolvedValue({ data: { courses: [] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Нет курсов')).toBeInTheDocument()
      expect(screen.getByText('Подключить Stepik')).toBeInTheDocument()
    })
  })

  it('renders course count', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 50 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('1 курсов')).toBeInTheDocument()
    })
  })

  it('renders course title', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'Python Course', status: 'Published', health_score: 95, stepik_course_id: 100, enrollment_count: 200 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Python Course')).toBeInTheDocument()
    })
  })

  it('renders enrollment count', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 42 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('42 студентов')).toBeInTheDocument()
    })
  })

  it('renders health score', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Published', health_score: 87.5, stepik_course_id: 100, enrollment_count: 10 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Score: 87.5')).toBeInTheDocument()
    })
  })

  it('renders Published status badge', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 100, enrollment_count: 5 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Published')).toBeInTheDocument()
    })
  })

  it('renders Draft status badge', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Draft', health_score: 90, stepik_course_id: 100, enrollment_count: 0 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Draft')).toBeInTheDocument()
    })
  })

  it('renders Stepik deep link', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Published', health_score: 90, stepik_course_id: 12345, enrollment_count: 1 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      const link = screen.getByText('Открыть на Stepik')
      expect(link).toHaveAttribute('href', 'https://stepik.org/course/12345')
      expect(link).toHaveAttribute('target', '_blank')
    })
  })

  it('renders multiple courses', async () => {
    mockGet.mockResolvedValue({
      data: {
        courses: [
          { id: '1', title: 'Python', status: 'Published', health_score: 95, stepik_course_id: 100, enrollment_count: 200 },
          { id: '2', title: 'JS', status: 'Draft', health_score: 80, stepik_course_id: 200, enrollment_count: 50 },
          { id: '3', title: 'ML', status: 'Published', health_score: 100, stepik_course_id: 300, enrollment_count: 7150 },
        ],
      },
    })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Python')).toBeInTheDocument()
      expect(screen.getByText('JS')).toBeInTheDocument()
      expect(screen.getByText('ML')).toBeInTheDocument()
      expect(screen.getByText('3 курсов')).toBeInTheDocument()
    })
  })

  it('renders zero enrollment count', async () => {
    mockGet.mockResolvedValue({ data: { courses: [{ id: '1', title: 'C1', status: 'Draft', health_score: 100, stepik_course_id: 100, enrollment_count: 0 }] } })
    render(<TestRouter><Courses /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('0 студентов')).toBeInTheDocument()
    })
  })
})
