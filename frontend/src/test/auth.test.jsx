import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { AuthProvider, useAuth } from '../contexts/AuthContext';

function TestConsumer() {
  const auth = useAuth();
  if (!auth) return null;
  return (
    <div>
      <div data-testid="loading">{String(auth.loading)}</div>
      <div data-testid="user">{auth.user ? JSON.stringify(auth.user) : 'null'}</div>
      <button data-testid="login-btn" onClick={auth.login}>
        Login
      </button>
      <button data-testid="logout-btn" onClick={auth.logout}>
        Logout
      </button>
    </div>
  );
}

describe('AuthContext', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows loading initially, then sets user on successful fetch', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1, email: 'test@test.com' }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId('loading').textContent).toBe('true');
    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
    expect(screen.getByTestId('user').textContent).toContain('test@test.com');
  });

  it('sets user to null on 401 (not logged in)', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
      headers: { get: () => 'application/json' },
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('user').textContent).toBe('null');
    });
    expect(screen.getByTestId('loading').textContent).toBe('false');
  });

  it('Regression: retries /auth/me while the backend is still starting', async () => {
    vi.useFakeTimers();
    global.fetch
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: { get: () => 'application/json' },
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: { get: () => 'application/json' },
        json: () => Promise.resolve({ id: 1, email: 'test@test.com' }),
      });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await vi.advanceTimersByTimeAsync(0);
    expect(screen.getByTestId('user').textContent).toBe('null');
    expect(screen.getByTestId('loading').textContent).toBe('true');

    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(2000);
    await vi.advanceTimersByTimeAsync(0);
    expect(screen.getByTestId('user').textContent).toContain('test@test.com');
    expect(screen.getByTestId('loading').textContent).toBe('false');
    vi.useRealTimers();
  });

  it('calls /api/auth/me on mount', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1 }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/auth/me', { credentials: 'include' });
    });
  });

  it('login sets window.location.href', () => {
    delete window.location;
    window.location = { href: '' };

    global.fetch.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1 }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    screen.getByTestId('login-btn').click();
    expect(window.location.href).toBe('/api/auth/login');
  });

  it('logout calls API and clears user', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1 }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('user').textContent).not.toBe('null');
    });

    global.fetch.mockResolvedValueOnce({ ok: true });
    screen.getByTestId('logout-btn').click();

    await waitFor(() => {
      expect(screen.getByTestId('user').textContent).toBe('null');
    });
  });

  it('logout calls POST /api/auth/logout', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1 }),
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('user').textContent).not.toBe('null');
    });

    global.fetch.mockResolvedValueOnce({ ok: true });
    screen.getByTestId('logout-btn').click();

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    });
  });
});
