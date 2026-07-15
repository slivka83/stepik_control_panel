import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Cohorts from '../pages/Cohorts'

describe('Cohorts', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    render(<TestRouter><Cohorts /></TestRouter>)
    expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
  })

  it('renders page title', async () => {
    mockGet.mockResolvedValue({ data: { active: 100, passive: 50, fading: 30, sleeping: 20 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Когортный анализ')).toBeInTheDocument()
    })
  })

  it('renders total student count', async () => {
    mockGet.mockResolvedValue({ data: { active: 100, passive: 50, fading: 30, sleeping: 20 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Всего: 200 студентов')).toBeInTheDocument()
    })
  })

  it('renders all four cohort labels', async () => {
    mockGet.mockResolvedValue({ data: { active: 100, passive: 50, fading: 30, sleeping: 20 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Активные')).toBeInTheDocument()
      expect(screen.getByText('Пассивные')).toBeInTheDocument()
      expect(screen.getByText('Затухающие')).toBeInTheDocument()
      expect(screen.getByText('Спящие')).toBeInTheDocument()
    })
  })

  it('renders cohort values', async () => {
    mockGet.mockResolvedValue({ data: { active: 7000, passive: 400, fading: 200, sleeping: 18 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('7000')).toBeInTheDocument()
      expect(screen.getByText('400')).toBeInTheDocument()
      expect(screen.getByText('200')).toBeInTheDocument()
      expect(screen.getByText('18')).toBeInTheDocument()
    })
  })

  it('renders cohort percentages', async () => {
    mockGet.mockResolvedValue({ data: { active: 50, passive: 50, fading: 0, sleeping: 0 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getAllByText(/50\.0%/).length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders day ranges', async () => {
    mockGet.mockResolvedValue({ data: { active: 10, passive: 5, fading: 3, sleeping: 2 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getAllByText(/7 дней/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/8–30 дней/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/30–90 дней/).length).toBeGreaterThanOrEqual(2)
      expect(screen.getAllByText(/90 дней/).length).toBeGreaterThanOrEqual(2)
    })
  })

  it('renders cohort definition section', async () => {
    mockGet.mockResolvedValue({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Определение когорт')).toBeInTheDocument()
      expect(screen.getByText(/Когортный статус определяется/)).toBeInTheDocument()
    })
  })

  it('renders predictive churn section', async () => {
    mockGet.mockResolvedValue({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Predictive Churn')).toBeInTheDocument()
      expect(screen.getByText(/ML-модель выявляет студентов/)).toBeInTheDocument()
    })
  })

  it('renders zero state correctly', async () => {
    mockGet.mockResolvedValue({ data: { active: 0, passive: 0, fading: 0, sleeping: 0 } })
    render(<TestRouter><Cohorts /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Всего: 0 студентов')).toBeInTheDocument()
    })
  })
})
