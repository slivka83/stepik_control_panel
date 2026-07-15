import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Dashboard from '../pages/Dashboard'

describe('Dashboard', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))

    render(
      <TestRouter>
        <Dashboard />
      </TestRouter>
    )
    expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
  })

  it('renders dashboard title', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0 } })
      .mockResolvedValueOnce({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
      .mockResolvedValueOnce({ data: { months: [] } })

    render(
      <TestRouter>
        <Dashboard />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Сводная аналитика')).toBeInTheDocument()
    })
  })

  it('renders KPI cards', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { total_revenue: 50000, total_students: 150, certificates_issued: 30, courses_count: 3 } })
      .mockResolvedValueOnce({ data: { active: 100, passive: 30, fading: 15, sleeping: 5 } })
      .mockResolvedValueOnce({ data: { months: [] } })

    render(
      <TestRouter>
        <Dashboard />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Доход за месяц')).toBeInTheDocument()
      expect(screen.getByText('Студенты')).toBeInTheDocument()
      expect(screen.getByText('Сертификаты')).toBeInTheDocument()
      expect(screen.getByText('Курсы')).toBeInTheDocument()
    })
  })

  it('renders alerts section', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0 } })
      .mockResolvedValueOnce({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
      .mockResolvedValueOnce({ data: { months: [] } })

    render(
      <TestRouter>
        <Dashboard />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Алерты')).toBeInTheDocument()
    })
  })

  it('renders deep links to stepik.org', async () => {
    mockGet
      .mockResolvedValueOnce({ data: { total_revenue: 0, total_students: 0, certificates_issued: 0, courses_count: 0 } })
      .mockResolvedValueOnce({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
      .mockResolvedValueOnce({ data: { months: [] } })

    render(
      <TestRouter>
        <Dashboard />
      </TestRouter>
    )

    await waitFor(() => {
      const links = screen.getAllByRole('link')
      const stepikLinks = links.filter(link => link.href.includes('stepik.org'))
      expect(stepikLinks.length).toBeGreaterThan(0)
    })
  })
})
