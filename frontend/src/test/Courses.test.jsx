import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Courses from '../pages/Courses'

describe('Courses', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))

    render(
      <TestRouter>
        <Courses />
      </TestRouter>
    )
    expect(screen.getByText('Загрузка курсов...')).toBeInTheDocument()
  })

  it('renders page title', async () => {
    mockGet.mockResolvedValue({ data: { courses: [] } })

    render(
      <TestRouter>
        <Courses />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Курсы')).toBeInTheDocument()
    })
  })

  it('shows empty state', async () => {
    mockGet.mockResolvedValue({ data: { courses: [] } })

    render(
      <TestRouter>
        <Courses />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Нет курсов')).toBeInTheDocument()
    })
  })

  it('renders connect button', async () => {
    mockGet.mockResolvedValue({ data: { courses: [] } })

    render(
      <TestRouter>
        <Courses />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Подключить Stepik')).toBeInTheDocument()
    })
  })

  it('renders course cards', async () => {
    mockGet.mockResolvedValue({
      data: {
        courses: [
          { id: '1', title: 'Python Course', status: 'Published', health_score: 95, stepik_course_id: 100 },
          { id: '2', title: 'JS Course', status: 'Draft', health_score: 80, stepik_course_id: 200 },
        ],
      },
    })

    render(
      <TestRouter>
        <Courses />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Python Course')).toBeInTheDocument()
      expect(screen.getByText('JS Course')).toBeInTheDocument()
    })
  })

  it('displays course count', async () => {
    mockGet.mockResolvedValue({
      data: {
        courses: [
          { id: '1', title: 'Course 1', status: 'Published', health_score: 90, stepik_course_id: 100 },
        ],
      },
    })

    render(
      <TestRouter>
        <Courses />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('1 курсов')).toBeInTheDocument()
    })
  })
})
