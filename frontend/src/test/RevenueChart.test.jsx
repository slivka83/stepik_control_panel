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

  it('renders with data', () => {
    const data = [
      { month: '2024-01-01', revenue: 10000 },
      { month: '2024-02-01', revenue: 15000 },
    ]
    render(<RevenueChart data={data} />)
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
  })
})
