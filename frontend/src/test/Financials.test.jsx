import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'

const mockGet = vi.fn()
vi.mock('../api', () => ({
  default: { get: (...args) => mockGet(...args) },
}))

import Financials from '../pages/Financials'

describe('Financials', () => {
  beforeEach(() => {
    mockGet.mockReset()
  })

  it('shows loading state', () => {
    mockGet.mockReturnValue(new Promise(() => {}))
    render(<TestRouter><Financials /></TestRouter>)
    expect(screen.getByText('Загрузка данных...')).toBeInTheDocument()
  })

  it('renders page title', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Финансовая аналитика')).toBeInTheDocument()
    })
  })

  it('renders revenue chart section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
    })
  })

  it('renders tax dashboard section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Налоговый дашборд')).toBeInTheDocument()
    })
  })

  it('renders B2B manager section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('B2B-Менеджер')).toBeInTheDocument()
    })
  })

  it('renders tax placeholders', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('ИНН')).toBeInTheDocument()
      expect(screen.getByText('БИК')).toBeInTheDocument()
      expect(screen.getByText('Система налогообложения')).toBeInTheDocument()
      expect(screen.getAllByText('Не указан').length).toBeGreaterThanOrEqual(2)
      expect(screen.getByText('Не указана')).toBeInTheDocument()
    })
  })

  it('renders tax warning', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText(/Заполните реквизиты/)).toBeInTheDocument()
    })
  })

  it('renders CSV upload section', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText('Импортируйте CSV-файл с email-адресами корпоративных клиентов')).toBeInTheDocument()
      expect(screen.getByText('Выбрать файл')).toBeInTheDocument()
    })
  })

  it('renders CSV format hint', async () => {
    mockGet.mockResolvedValue({ data: { months: [] } })
    render(<TestRouter><Financials /></TestRouter>)
    await waitFor(() => {
      expect(screen.getByText(/Формат: CSV с колонкой/)).toBeInTheDocument()
    })
  })
})
