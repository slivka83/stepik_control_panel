import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StudentsChart from '../components/StudentsChart'

describe('StudentsChart', () => {
  it('renders empty state when no data', () => {
    render(<StudentsChart data={{}} />)
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument()
  })

  it('renders chart title', () => {
    render(<StudentsChart data={{}} />)
    expect(screen.getByText('Студенты')).toBeInTheDocument()
  })

  it('renders with cohort data', () => {
    const data = { active: 100, passive: 50, fading: 30, sleeping: 20 }
    render(<StudentsChart data={data} />)
    expect(screen.getByText('Студенты')).toBeInTheDocument()
    expect(screen.getByText('Активные')).toBeInTheDocument()
    expect(screen.getByText('Пассивные')).toBeInTheDocument()
    expect(screen.getByText('Затухающие')).toBeInTheDocument()
    expect(screen.getByText('Спящие')).toBeInTheDocument()
  })

  it('displays counts', () => {
    const data = { active: 100, passive: 0, fading: 0, sleeping: 0 }
    render(<StudentsChart data={data} />)
    expect(screen.getByText('100')).toBeInTheDocument()
  })

  it('displays percentages correctly', () => {
    const data = { active: 50, passive: 50, fading: 0, sleeping: 0 }
    render(<StudentsChart data={data} />)
    expect(screen.getAllByText('50%')).toHaveLength(2)
  })

  it('displays 100% for single cohort', () => {
    const data = { active: 200, passive: 0, fading: 0, sleeping: 0 }
    render(<StudentsChart data={data} />)
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('displays 0% when total is 0', () => {
    const data = { active: 0, passive: 0, fading: 0, sleeping: 0 }
    render(<StudentsChart data={data} />)
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument()
  })

  it('renders glass-panel container', () => {
    const { container } = render(<StudentsChart data={{ active: 10 }} />)
    expect(container.querySelector('.glass-panel')).toBeInTheDocument()
  })
})
