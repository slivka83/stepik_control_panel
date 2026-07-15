import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Cohorts from '../pages/Cohorts'

describe('Cohorts', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))

    render(
      <TestRouter>
        <Cohorts />
      </TestRouter>
    )
    expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
  })

  it('renders page title', async () => {
    mockGet.mockResolvedValue({
      data: { active: 100, passive: 50, fading: 30, sleeping: 20 },
    })

    render(
      <TestRouter>
        <Cohorts />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Когортный анализ')).toBeInTheDocument()
    })
  })

  it('renders cohort segments', async () => {
    mockGet.mockResolvedValue({
      data: { active: 100, passive: 50, fading: 30, sleeping: 20 },
    })

    render(
      <TestRouter>
        <Cohorts />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Активные')).toBeInTheDocument()
      expect(screen.getByText('Пассивные')).toBeInTheDocument()
      expect(screen.getByText('Затухающие')).toBeInTheDocument()
      expect(screen.getByText('Спящие')).toBeInTheDocument()
    })
  })

  it('displays total student count', async () => {
    mockGet.mockResolvedValue({
      data: { active: 100, passive: 50, fading: 30, sleeping: 20 },
    })

    render(
      <TestRouter>
        <Cohorts />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Всего: 200 студентов')).toBeInTheDocument()
    })
  })

  it('renders predictive churn section', async () => {
    mockGet.mockResolvedValue({
      data: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    })

    render(
      <TestRouter>
        <Cohorts />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Predictive Churn')).toBeInTheDocument()
    })
  })
})
