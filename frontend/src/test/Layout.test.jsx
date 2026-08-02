import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import TestRouter from './TestRouter';
import Layout from '../components/Layout';

const defaultSyncValue = {
  syncStatus: { in_progress: false, last_sync: '2026-07-21T10:00:00' },
  data: { kpi: null, cohorts: {}, revenue: { months: [] }, alerts: [], courses: [], financials: null },
  loading: false,
  error: null,
  refresh: vi.fn(),
};

const NAV_LINKS = {
  Дашборд: '/',
  Курсы: '/courses',
  Решения: '/solutions',
  Финансы: '/financials',
  Студенты: '/students',
  Активности: '/activities',
};

function mockAuthMe(authenticated) {
  if (!authenticated) {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('no auth'));
    return;
  }
  vi.spyOn(global, 'fetch').mockResolvedValue({
    ok: true,
    headers: { get: (name) => (name === 'content-type' ? 'application/json' : null) },
    json: () => Promise.resolve({ id: '1', stepik_id: 64381531, authenticated: true }),
  });
}

function renderLayout(authenticated, syncValue) {
  mockAuthMe(authenticated);
  return render(
    <TestRouter syncValue={syncValue || defaultSyncValue}>
      <Layout>
        <div>Content</div>
      </Layout>
    </TestRouter>,
  );
}

describe('Layout', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children', async () => {
    renderLayout(false);
    await waitFor(() => {
      expect(screen.getByText('Content')).toBeInTheDocument();
    });
  });

  it('renders sidebar nav links', async () => {
    renderLayout(false);
    await waitFor(() => {
      for (const label of Object.keys(NAV_LINKS)) {
        expect(screen.getByRole('link', { name: label })).toBeInTheDocument();
      }
    });
  });

  it('renders nav links with correct hrefs', async () => {
    renderLayout(false);
    await waitFor(() => {
      for (const [label, href] of Object.entries(NAV_LINKS)) {
        expect(screen.getByRole('link', { name: label })).toHaveAttribute('href', href);
      }
    });
  });

  it('shows login button when not authenticated', async () => {
    renderLayout(false);
    await waitFor(() => {
      expect(screen.getByTitle('Войти')).toBeInTheDocument();
    });
    expect(screen.queryByTitle('Выйти')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Обновить')).not.toBeInTheDocument();
  });

  it('shows sync and logout buttons when authenticated', async () => {
    renderLayout(true);
    await waitFor(() => {
      expect(screen.getByTitle('Выйти')).toBeInTheDocument();
    });
    expect(screen.getByTitle('Обновить')).toBeInTheDocument();
    expect(screen.queryByTitle('Войти')).not.toBeInTheDocument();
  });

  it('marks active nav link', async () => {
    renderLayout(false);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Дашборд' })).toHaveClass('text-cyber-blue');
    });
  });

  it('shows background sync progress and disables the button on page open mid-sync', async () => {
    const syncingValue = {
      ...defaultSyncValue,
      syncStatus: { in_progress: true, progress: 57, step: 'решения: загрузка', last_sync: '2026-07-21T10:00:00' },
    };
    renderLayout(true, syncingValue);
    await waitFor(() => {
      expect(screen.getByTitle(/Завершено: 57%/)).toBeInTheDocument();
    });
    const btn = screen.getByTitle(/Завершено: 57%/);
    expect(btn).toBeDisabled();
    expect(btn.querySelector('.animate-spin')).toBeInTheDocument();
    expect(btn.querySelector('span[style]')).toHaveStyle('height: 57%');
    expect(btn.getAttribute('title')).toContain('Прошло: 0 с');
    expect(btn.getAttribute('title')).toContain('Осталось: ~0 с');
    expect(btn.getAttribute('title')).not.toContain('решения');
  });

  it('updates elapsed and remaining time in tooltip while syncing', async () => {
    vi.useFakeTimers();
    try {
      const syncingValue = {
        ...defaultSyncValue,
        syncStatus: { in_progress: true, progress: 57, step: '', last_sync: null },
      };
      renderLayout(true, syncingValue);
      await act(async () => {});
      expect(screen.getByTitle(/Завершено: 57%/)).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(3000);
      });
      const btn = screen.getByTitle(/Прошло: 3 с/);
      expect(btn.getAttribute('title')).toContain('Осталось: ~2 с');
    } finally {
      vi.useRealTimers();
    }
  });

  it('keeps the sync button idle and enabled when no sync is running', async () => {
    renderLayout(true);
    await waitFor(() => {
      expect(screen.getByTitle('Обновить')).toBeInTheDocument();
    });
    expect(screen.getByTitle('Обновить')).not.toBeDisabled();
    expect(screen.getByTitle('Обновить').querySelector('.animate-spin')).not.toBeInTheDocument();
  });

  it('applies visual scale to course and student icons only', async () => {
    renderLayout(false);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Курсы' })).toBeInTheDocument();
    });
    expect(screen.getByRole('link', { name: 'Курсы' }).querySelector('span')).toHaveStyle('transform: scale(0.75)');
    expect(screen.getByRole('link', { name: 'Студенты' }).querySelector('span')).toHaveStyle('transform: scale(0.85)');
    expect(screen.getByRole('link', { name: 'Дашборд' }).querySelector('span')).not.toHaveStyle(
      'transform: scale(0.75)',
    );
    expect(screen.getByRole('link', { name: 'Решения' }).querySelector('span')).not.toHaveStyle(
      'transform: scale(0.75)',
    );
  });
});
