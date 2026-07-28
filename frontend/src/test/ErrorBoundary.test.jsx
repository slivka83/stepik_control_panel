import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import ErrorBoundary from '../components/ErrorBoundary'

const GoodChild = () => <div>Good content</div>
const BadChild = () => {
  throw new Error('Test error message')
}

describe('ErrorBoundary', () => {
  beforeAll(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterAll(() => {
    vi.restoreAllMocks()
  })

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <GoodChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Good content')).toBeInTheDocument()
  })

  it('renders error UI when child throws', () => {
    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Ошибка приложения')).toBeInTheDocument()
  })

  it('displays error message', () => {
    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('renders reload button', () => {
    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Перезагрузить')).toBeInTheDocument()
  })

  it('reload button triggers window.location.reload', () => {
    const reloadMock = vi.fn()
    Object.defineProperty(window, 'location', {
      value: { reload: reloadMock },
      writable: true,
    })

    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )

    screen.getByText('Перезагрузить').click()
    expect(reloadMock).toHaveBeenCalled()
  })

  it('renders stack trace details', () => {
    render(
      <ErrorBoundary>
        <BadChild />
      </ErrorBoundary>
    )
    expect(screen.getByText('Трассировка стека')).toBeInTheDocument()
  })
})
