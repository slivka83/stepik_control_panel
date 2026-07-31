import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'
import Layout from '../components/Layout'

const defaultSyncValue = {
  syncStatus: { in_progress: false, last_sync: '2026-07-21T10:00:00' },
  data: { kpi: null, cohorts: {}, revenue: { months: [] }, alerts: [], courses: [], financials: null },
  loading: false,
  error: null,
  refresh: vi.fn(),
}

const NAV_LINKS = {
  'Дашборд': '/',
  'Курсы': '/courses',
  'Решения': '/solutions',
  'Финансы': '/financials',
  'Студенты': '/students',
  'Активности': '/activities',
}

function mockAuthMe(authenticated) {
  if (!authenticated) {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    return
  }
  vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    headers: { get: (name) => (name === 'content-type' ? 'application/json' : null) },
    json: () => Promise.resolve({ id: '1', stepik_id: 64381531, authenticated: true }),
  })
}

function renderLayout(authenticated) {
  mockAuthMe(authenticated)
  return render(
    <TestRouter syncValue={defaultSyncValue}>
      <Layout><div>Content</div></Layout>
    </TestRouter>
  )
}

describe('Layout', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders children', async () => {
    renderLayout(false)
    await waitFor(() => {
      expect(screen.getByText('Content')).toBeInTheDocument()
    })
  })

  it('renders sidebar nav links', async () => {
    renderLayout(false)
    await waitFor(() => {
      for (const label of Object.keys(NAV_LINKS)) {
        expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
      }
    })
  })

  it('renders nav links with correct hrefs', async () => {
    renderLayout(false)
    await waitFor(() => {
      for (const [label, href] of Object.entries(NAV_LINKS)) {
        expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href)
      }
    })
  })

  it('shows login button when not authenticated', async () => {
    renderLayout(false)
    await waitFor(() => {
      expect(screen.getByTitle('Войти')).toBeInTheDocument()
    })
    expect(screen.queryByTitle('Выйти')).not.toBeInTheDocument()
    expect(screen.queryByTitle('Обновить')).not.toBeInTheDocument()
  })

  it('shows sync and logout buttons when authenticated', async () => {
    renderLayout(true)
    await waitFor(() => {
      expect(screen.getByTitle('Выйти')).toBeInTheDocument()
    })
    expect(screen.getByTitle('Обновить')).toBeInTheDocument()
    expect(screen.queryByTitle('Войти')).not.toBeInTheDocument()
  })

  it('marks active nav link', async () => {
    renderLayout(false)
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Дашборд' })).toHaveClass('text-cyber-blue')
    })
  })
})
