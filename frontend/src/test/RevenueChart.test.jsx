import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RevenueChart from '../components/RevenueChart'

describe('RevenueChart', () => {
  it('renders empty state when no data', () => {
    render(<RevenueChart data={[]} />)
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument()
  })

  it('renders chart title', () => {
    render(<RevenueChart data={[]} />)
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
  })

  it('renders chart with data', () => {
    const data = [
      { month: '2026-01-01T00:00:00', revenue: 12000 },
      { month: '2026-02-01T00:00:00', revenue: 18000 },
    ]
    render(<RevenueChart data={data} />)
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
    expect(screen.queryByText('Нет данных для отображения')).not.toBeInTheDocument()
  })

  it('renders glass-panel container', () => {
    const { container } = render(<RevenueChart data={[]} />)
    expect(container.querySelector('.glass-panel')).toBeInTheDocument()
  })

  it('renders with empty revenue values', () => {
    const data = [
      { month: '2026-01-01T00:00:00', revenue: 0 },
    ]
    render(<RevenueChart data={data} />)
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
  })
})
