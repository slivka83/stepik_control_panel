import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CohortChart from '../components/CohortChart'

describe('CohortChart', () => {
  it('renders empty state when no data', () => {
    render(<CohortChart data={{}} />)
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument()
  })

  it('renders chart title', () => {
    render(<CohortChart data={{}} />)
    expect(screen.getByText('Когортная сегментация')).toBeInTheDocument()
  })

  it('renders with cohort data', () => {
    const data = {
      active: 100,
      passive: 50,
      fading: 30,
      sleeping: 20,
    }
    render(<CohortChart data={data} />)
    expect(screen.getByText('Когортная сегментация')).toBeInTheDocument()
    expect(screen.getByText('Активные')).toBeInTheDocument()
    expect(screen.getByText('Пассивные')).toBeInTheDocument()
    expect(screen.getByText('Затухающие')).toBeInTheDocument()
    expect(screen.getByText('Спящие')).toBeInTheDocument()
  })

  it('displays percentages', () => {
    const data = {
      active: 50,
      passive: 50,
      fading: 0,
      sleeping: 0,
    }
    render(<CohortChart data={data} />)
    expect(screen.getAllByText('50%')).toHaveLength(2)
  })

  it('displays counts', () => {
    const data = {
      active: 100,
      passive: 0,
      fading: 0,
      sleeping: 0,
    }
    render(<CohortChart data={data} />)
    expect(screen.getByText('100')).toBeInTheDocument()
  })
})
