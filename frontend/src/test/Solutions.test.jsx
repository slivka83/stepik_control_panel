import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { SyncContext } from '../contexts/SyncContext'
import { AuthProvider } from '../contexts/AuthContext'
import Solutions from '../pages/Solutions'

const mockSubmissions = {
  months: [
    { month: 'Январь 2026', total: 10, correct: 7 },
    { month: 'Февраль 2026', total: 20, correct: 15 },
  ],
  years: [
    { year: 2026, total: 30, correct: 22 },
  ],
  by_course: [
    { course_id: 1, title: 'Тестовый курс', total: 30, correct: 22 },
  ],
}

const makeSyncValue = (submissions = mockSubmissions) => ({
  syncStatus: { in_progress: false, last_sync: null },
  data: {
    kpi: {},
    cohorts: { active: 0, passive: 0, fading: 0, sleeping: 0 },
    revenue: { months: [] },
    alerts: [],
    courses: [],
    submissions,
  },
  loading: false,
  error: null,
  refresh: vi.fn(),
})

function renderSolutions(submissions) {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SyncContext.Provider value={makeSyncValue(submissions)}>
          <Solutions />
        </SyncContext.Provider>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('Solutions', () => {
  it('renders months by default', () => {
    renderSolutions()
    expect(screen.getByText('Январь 2026')).toBeInTheDocument()
    expect(screen.getByText('Февраль 2026')).toBeInTheDocument()
    expect(screen.getByText('Месяц')).toBeInTheDocument()
  })

  it('renders tab buttons when has data', () => {
    renderSolutions()
    expect(screen.getByText('По месяцам')).toBeInTheDocument()
    expect(screen.getByText('По годам')).toBeInTheDocument()
    expect(screen.getByText('По курсам')).toBeInTheDocument()
    expect(screen.getByText('Самые сложные')).toBeInTheDocument()
  })

  it('switches to years tab on click', async () => {
    const user = userEvent.setup()
    renderSolutions()
    await user.click(screen.getByText('По годам'))
    expect(screen.getByText('2026')).toBeInTheDocument()
    expect(screen.getAllByText('30').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('22').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Год')).toBeInTheDocument()
  })

  it('switches to courses tab on click', async () => {
    const user = userEvent.setup()
    renderSolutions()
    await user.click(screen.getByText('По курсам'))
    expect(screen.getByText('Тестовый курс')).toBeInTheDocument()
  })

  it('renders empty state when no submissions', () => {
    renderSolutions({ months: [], by_course: [], years: [] })
    expect(
      screen.getByText('Данные о решениях отсутствуют. Запустите синхронизацию.')
    ).toBeInTheDocument()
  })
})
