import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import StudentsBar from '../components/StudentsBar'

describe('StudentsBar', () => {
  it('renders empty state when total is 0', () => {
    render(<StudentsBar data={{ active: 0, passive: 0 }} />)
    expect(screen.getByText('Нет данных для отображения')).toBeInTheDocument()
    expect(screen.getByText('Студенты')).toBeInTheDocument()
  })

  it('renders title and total count', () => {
    render(<StudentsBar data={{ active: 100, passive: 50 }} />)
    expect(screen.getByText('Студенты')).toBeInTheDocument()
    expect(screen.getByText('150 студентов')).toBeInTheDocument()
  })

  it('renders glass-panel container', () => {
    const { container } = render(<StudentsBar data={{ active: 100 }} />)
    expect(container.querySelector('.glass-panel')).toBeInTheDocument()
  })

  it('sorts entries by cohort order', () => {
    const { container } = render(
      <StudentsBar data={{ sleeping: 10, active: 100, passive: 50 }} />
    )
    const labels = container.querySelectorAll('.text-\\[10px\\]')
    expect(screen.getByText('Активные')).toBeInTheDocument()
    expect(screen.getByText('Пассивные')).toBeInTheDocument()
    expect(screen.getByText('Спящие')).toBeInTheDocument()
  })

  it('renders percentages for each cohort', () => {
    render(<StudentsBar data={{ active: 100, passive: 100 }} />)
    const pcts = screen.getAllByText('50%')
    expect(pcts.length).toBe(2)
  })

  it('handles zombie cohort', () => {
    render(<StudentsBar data={{ active: 100, zombie: 5 }} />)
    expect(screen.getByText('Зомби')).toBeInTheDocument()
  })

  it('shows single cohort full width', () => {
    render(<StudentsBar data={{ active: 100 }} />)
    expect(screen.getByText('Студенты')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
  })

  it('toggles cohort visibility on click', () => {
    render(<StudentsBar data={{ active: 80, passive: 20 }} />)
    const passiveLabel = screen.getByText('Пассивные')
    fireEvent.click(passiveLabel)
    expect(screen.getByText('80 студентов')).toBeInTheDocument()
  })
})
