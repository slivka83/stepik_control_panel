import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('axios', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Financials from '../pages/Financials'

describe('Financials', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state initially', () => {
    mockGet.mockReturnValue(new Promise(() => {}))

    render(
      <TestRouter>
        <Financials />
      </TestRouter>
    )
    expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
  })

  it('renders financials page title', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })

    render(
      <TestRouter>
        <Financials />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Финансовая аналитика')).toBeInTheDocument()
    })
  })

  it('renders revenue chart section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })

    render(
      <TestRouter>
        <Financials />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
    })
  })

  it('renders tax dashboard section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })

    render(
      <TestRouter>
        <Financials />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Налоговый дашборд')).toBeInTheDocument()
    })
  })

  it('renders B2B manager section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })

    render(
      <TestRouter>
        <Financials />
      </TestRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('B2B-Менеджер')).toBeInTheDocument()
    })
  })
})
