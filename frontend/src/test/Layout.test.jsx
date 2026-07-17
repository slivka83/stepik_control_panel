import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import TestRouter from './TestRouter'
import Layout from '../components/Layout'

describe('Layout', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('renders children', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Test Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('Test Content')).toBeInTheDocument()
    })
  })

  it('renders sidebar nav links', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('Дашборд')).toBeInTheDocument()
      expect(screen.getByText('Курсы')).toBeInTheDocument()
      expect(screen.getByText('Финансы')).toBeInTheDocument()
      expect(screen.getByText('Когорты')).toBeInTheDocument()
    })
  })

  it('shows login button when not authenticated', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('Войти')).toBeInTheDocument()
    })
  })

  it('shows SYNCED when authenticated', async () => {
    localStorage.setItem('stepik_session_token', 'test-token-123')
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: '1', stepik_id: 123, authenticated: true }),
    })
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('SYNCED')).toBeInTheDocument()
    })
  })

  it('shows Stepik ID when authenticated', async () => {
    localStorage.setItem('stepik_session_token', 'test-token-123')
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: '1', stepik_id: 64381531, authenticated: true }),
    })
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('ID: 64381531')).toBeInTheDocument()
    })
  })

  it('shows logout button when authenticated', async () => {
    localStorage.setItem('stepik_session_token', 'test-token-123')
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ id: '1', stepik_id: 123, authenticated: true }),
    })
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('Выйти')).toBeInTheDocument()
    })
  })

  it('hides SYNCED when not authenticated', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('Войти')).toBeInTheDocument()
    })
    expect(screen.queryByText('SYNCED')).not.toBeInTheDocument()
  })

  it('renders version', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('v0.2.0')).toBeInTheDocument()
    })
  })

  it('renders read-only mode label', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      expect(screen.getByText('Read-Only Mode')).toBeInTheDocument()
    })
  })

  it('renders nav links with correct hrefs', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'))
    render(
      <TestRouter>
        <Layout><div>Content</div></Layout>
      </TestRouter>
    )
    await waitFor(() => {
      const dashLink = screen.getByText('Дашборд').closest('a')
      expect(dashLink).toHaveAttribute('href', '/')
      const coursesLink = screen.getByText('Курсы').closest('a')
      expect(coursesLink).toHaveAttribute('href', '/courses')
      const finLink = screen.getByText('Финансы').closest('a')
      expect(finLink).toHaveAttribute('href', '/financials')
      const cohortLink = screen.getByText('Когорты').closest('a')
      expect(cohortLink).toHaveAttribute('href', '/cohorts')
    })
  })
})
