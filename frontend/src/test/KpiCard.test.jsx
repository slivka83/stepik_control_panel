import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import KpiCard from '../components/KpiCard'

describe('KpiCard', () => {
  it('renders title', () => {
    render(<KpiCard title="Test Title" value={100} />)
    expect(screen.getByText('Test Title')).toBeInTheDocument()
  })

  it('renders with prefix', () => {
    render(<KpiCard title="Revenue" value={5000} prefix="$" />)
    expect(screen.getByText('$')).toBeInTheDocument()
  })

  it('renders with suffix', () => {
    render(<KpiCard title="Revenue" value={5000} suffix=" ₽" />)
    expect(screen.getByText('₽')).toBeInTheDocument()
  })

  it('applies glass-panel class', () => {
    const { container } = render(<KpiCard title="Test" value={100} />)
    expect(container.firstChild).toHaveClass('glass-panel')
  })

  it('renders trend up', () => {
    const { container } = render(<KpiCard title="Growth" value={100} trend={12} />)
    expect(container.textContent).toContain('12%')
  })

  it('renders trend down', () => {
    const { container } = render(<KpiCard title="Decline" value={100} trend={-5} />)
    expect(container.textContent).toContain('5%')
  })
})
