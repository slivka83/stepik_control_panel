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
      { month: 'Январь 2026', income: 12000 },
      { month: 'Февраль 2026', income: 18000 },
    ]
    render(<RevenueChart data={data} />)
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
    expect(screen.queryByText('Нет данных для отображения')).not.toBeInTheDocument()
  })

  it('renders glass-panel container', () => {
    const { container } = render(<RevenueChart data={[]} />)
    expect(container.querySelector('.glass-panel')).toBeInTheDocument()
  })

  it('renders with zero income values', () => {
    const data = [
      { month: 'Март 2026', income: 0 },
    ]
    render(<RevenueChart data={data} />)
    expect(screen.getByText('Доход по месяцам')).toBeInTheDocument()
  })

  it('wraps chart in figure with aria-label', () => {
    const data = [{ month: 'Январь 2026', income: 1000, year: 2026 }]
    const { container } = render(<RevenueChart data={data} />)
    const figure = container.querySelector('figure')
    expect(figure).toBeInTheDocument()
    expect(figure).toHaveAttribute('aria-label', 'Диаграмма доходов по месяцам')
  })

  it('renders figcaption with window size and total income summary', () => {
    const data = [
      { month: 'Январь 2026', income: 1000, year: 2026 },
      { month: 'Февраль 2026', income: 2000, year: 2026 },
    ]
    const { container } = render(<RevenueChart data={data} />)
    const figcaption = container.querySelector('figcaption')
    expect(figcaption).toBeInTheDocument()
    expect(figcaption.textContent).toContain('18')
    expect(figcaption.textContent).toMatch(/3\s*000/)
  })
})
