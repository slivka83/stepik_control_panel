import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import KpiCard from '../components/KpiCard'

describe('KpiCard', () => {
  it('renders title text', () => {
    render(<KpiCard title="Доход за месяц" value={50000} />)
    expect(screen.getByText('Доход за месяц')).toBeInTheDocument()
  })

  it('renders numeric value with CountUp', () => {
    render(<KpiCard title="Студенты" value={150} />)
    expect(screen.getByText('Студенты')).toBeInTheDocument()
  })

  it('renders prefix', () => {
    render(<KpiCard title="Revenue" value={5000} prefix="$" />)
    expect(screen.getByText('$')).toBeInTheDocument()
  })

  it('renders suffix', () => {
    render(<KpiCard title="Revenue" value={5000} suffix=" ₽" />)
    expect(screen.getByText('₽')).toBeInTheDocument()
  })

  it('applies glass-panel class', () => {
    const { container } = render(<KpiCard title="Test" value={100} />)
    expect(container.firstChild).toHaveClass('glass-panel')
  })

  it('renders trend up indicator', () => {
    const { container } = render(<KpiCard title="Growth" value={100} trend={12} />)
    expect(container.textContent).toContain('12%')
  })

  it('renders trend down indicator', () => {
    const { container } = render(<KpiCard title="Decline" value={100} trend={-5} />)
    expect(container.textContent).toContain('5%')
  })

  it('renders zero value', () => {
    render(<KpiCard title="Empty" value={0} />)
    expect(screen.getByText('Empty')).toBeInTheDocument()
  })

  it('renders large numbers', () => {
    render(<KpiCard title="Big" value={1000000} />)
    expect(screen.getByText('Big')).toBeInTheDocument()
  })

  it('does not render trend when trend prop is absent', () => {
    const { container } = render(<KpiCard title="No trend" value={100} />)
    expect(container.textContent).not.toContain('%')
  })

  it.each([
    ['cyber-blue', 'text-cyber-blue'],
    ['neon-green', 'text-neon-green'],
    ['amber-alert', 'text-amber-alert'],
    ['crimson-alert', 'text-crimson-alert'],
  ])('renders with color %s', (color, expectedClass) => {
    const { container } = render(<KpiCard title="Test" value={100} color={color} />)
    expect(container.querySelector('.font-mono')).toHaveClass(expectedClass)
  })
})
