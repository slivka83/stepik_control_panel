import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { SyncProvider, useSync } from '../contexts/SyncContext'
import { AuthProvider } from '../contexts/AuthContext'

const mockApiInstance = vi.hoisted(() => ({
  get: vi.fn(),
  interceptors: { response: { use: vi.fn() } },
}))

vi.mock('../api', () => ({
  default: mockApiInstance,
}))

function TestConsumer() {
  const sync = useSync()
  return (
    <div>
      <div data-testid="loading">{String(sync.loading)}</div>
      <div data-testid="error">{sync.error || 'no-error'}</div>
      <div data-testid="data-kpi">{sync.data.kpi ? 'loaded' : 'null'}</div>
    </div>
  )
}

describe('SyncContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1, email: 'test@test.com' }),
    })
  })

  it('renders without crashing', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} })

    render(
      <AuthProvider>
        <SyncProvider>
          <div data-testid="mounted">mounted</div>
        </SyncProvider>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('mounted')).toBeInTheDocument()
    })
  })

  it('calls api.get for endpoints when authenticated', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} })

    render(
      <AuthProvider>
        <SyncProvider>
          <div data-testid="mounted">mounted</div>
        </SyncProvider>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(mockApiInstance.get).toHaveBeenCalledWith('/dashboard/kpi', expect.any(Object))
    })
  })

  it('sets loading to false after auth resolves', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} })

    render(
      <AuthProvider>
        <SyncProvider>
          <TestConsumer />
        </SyncProvider>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false')
    })
  })

  it('sets error when data fetch fails', async () => {
    mockApiInstance.get.mockRejectedValue(new Error('fetch failed'))

    render(
      <AuthProvider>
        <SyncProvider>
          <TestConsumer />
        </SyncProvider>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).not.toBe('no-error')
    })
  })

  it('sets data.kpi when kpi endpoint succeeds', async () => {
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/dashboard/kpi') return Promise.resolve({ data: { total_revenue: 100 } })
      return Promise.resolve({ data: {} })
    })

    render(
      <AuthProvider>
        <SyncProvider>
          <TestConsumer />
        </SyncProvider>
      </AuthProvider>
    )

    await waitFor(() => {
      expect(screen.getByTestId('data-kpi').textContent).toBe('loaded')
    })
  })
})
