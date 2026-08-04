import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import TestRouter from './TestRouter';
import Layout from '../components/Layout';
import api from '../api';

vi.mock('../api', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
  },
}));

const defaultSyncValue = {
  syncStatus: { in_progress: false, last_sync: '2026-07-21T10:00:00' },
  data: { kpi: null, cohorts: {}, revenue: { months: [] }, alerts: [], courses: [], financials: null },
  loading: false,
  error: null,
  refresh: vi.fn(),
  updateSyncStatus: vi.fn(),
  selectedCourseIds: null,
  isFilterActive: false,
  toggleCourse: vi.fn(),
  selectAllCourses: vi.fn(),
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
    expect(screen.queryByTitle(/Обновить/)).not.toBeInTheDocument();
  });

  it('shows sync and logout buttons when authenticated', async () => {
    renderLayout(true);
    await waitFor(() => {
      expect(screen.getByTitle('Выйти')).toBeInTheDocument();
    });
    expect(screen.getByTitle(/Обновить/)).toBeInTheDocument();
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
      expect(screen.getByTitle(/Обновить/)).toBeInTheDocument();
    });
    expect(screen.getByTitle(/Обновить/)).not.toBeDisabled();
    expect(screen.getByTitle(/Обновить/).querySelector('.animate-spin')).not.toBeInTheDocument();
  });

  it('shows the last sync date in the idle sync tooltip', async () => {
    renderLayout(true);
    await waitFor(() => {
      expect(screen.getByTitle(/Обновить/)).toBeInTheDocument();
    });
    const btn = screen.getByTitle(/Обновить/);
    expect(btn.getAttribute('title')).toContain('Последняя синхронизация: 21.07.2026, 10:00');
  });

  it('keeps the idle tooltip simple when sync never ran', async () => {
    const neverSyncedValue = {
      ...defaultSyncValue,
      syncStatus: { in_progress: false, progress: 0, step: '', last_sync: null, last_error: null },
    };
    renderLayout(true, neverSyncedValue);
    await waitFor(() => {
      expect(screen.getByTitle('Обновить')).toBeInTheDocument();
    });
  });

  it('shows the fresh sync date in the tooltip right after a sync finishes', async () => {
    mockAuthMe(true);
    vi.mocked(api.post).mockResolvedValue({ data: { status: 'sync_started' } });
    vi.mocked(api.get).mockResolvedValue({
      data: { in_progress: false, progress: 100, step: 'готово', last_sync: '2026-08-05T00:05:13' },
    });

    function LayoutWithLiveSync() {
      const [syncStatus, setSyncStatus] = useState({ in_progress: false, last_sync: null });
      const value = { ...defaultSyncValue, syncStatus, updateSyncStatus: setSyncStatus };
      return (
        <TestRouter syncValue={value}>
          <Layout>
            <div>Content</div>
          </Layout>
        </TestRouter>
      );
    }

    render(<LayoutWithLiveSync />);
    const btn = await screen.findByTitle('Обновить');
    act(() => {
      btn.click();
    });
    await waitFor(
      () => {
        expect(screen.getByTitle(/Последняя синхронизация: 05.08.2026, 00:05/)).toBeInTheDocument();
      },
      { timeout: 5000 },
    );
    expect(api.get).toHaveBeenCalled();
  });

  it('fills the sync button pink and shows the error tooltip after a failed sync', async () => {
    const failedValue = {
      ...defaultSyncValue,
      syncStatus: {
        in_progress: false,
        progress: 0,
        step: '',
        last_sync: '2026-07-21T10:00:00',
        last_error: 'Temporary failure in name resolution',
      },
    };
    renderLayout(true, failedValue);
    await waitFor(() => {
      expect(screen.getByTitle(/Синхронизация не удалась/)).toBeInTheDocument();
    });
    const btn = screen.getByTitle(/Синхронизация не удалась/);
    expect(btn.getAttribute('title')).toContain('Temporary failure in name resolution');
    expect(btn).not.toBeDisabled();
    expect(btn.querySelector('.animate-spin')).not.toBeInTheDocument();
    const fill = btn.querySelector('.bg-crimson-alert\\/30');
    expect(fill).toBeInTheDocument();
    expect(fill).toHaveStyle('height: 100%');
    expect(btn.querySelector('.bg-cyber-blue\\/25')).not.toBeInTheDocument();
  });

  it('hides the pink error fill and reverts tooltip when a new sync starts', async () => {
    mockAuthMe(true);
    const failedValue = {
      ...defaultSyncValue,
      syncStatus: {
        in_progress: false,
        progress: 0,
        step: '',
        last_sync: '2026-07-21T10:00:00',
        last_error: 'boom',
      },
    };
    const { rerender } = render(
      <TestRouter syncValue={failedValue}>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTitle(/Синхронизация не удалась/)).toBeInTheDocument();
    });
    rerender(
      <TestRouter syncValue={{ ...failedValue, syncStatus: { ...failedValue.syncStatus, in_progress: true, progress: 10 } }}>
        <Layout>
          <div>Content</div>
        </Layout>
      </TestRouter>,
    );
    await waitFor(() => {
      expect(screen.getByTitle(/Завершено: 10%/)).toBeInTheDocument();
    });
    const btn = screen.getByTitle(/Завершено: 10%/);
    expect(btn.querySelector('.bg-crimson-alert\\/30')).not.toBeInTheDocument();
    expect(btn.querySelector('.bg-cyber-blue\\/25')).toBeInTheDocument();
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

  it('opens course filter menu from the filter button and shows courses', async () => {
    const syncValue = {
      ...defaultSyncValue,
      data: {
        ...defaultSyncValue.data,
        courses: [
          { id: 'c1', stepik_course_id: 101, title: 'Python' },
          { id: 'c2', stepik_course_id: 102, title: 'SQL' },
        ],
      },
    };
    renderLayout(true, syncValue);
    const filterBtn = await screen.findByTitle('Фильтр по курсам');
    fireEvent.click(filterBtn);
    await waitFor(() => {
      expect(screen.getByRole('menu')).toBeInTheDocument();
    });
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('SQL')).toBeInTheDocument();
    expect(screen.getByText('2 из 2')).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    });
  });

  it('highlights the filter button when a subset is active', async () => {
    const syncValue = {
      ...defaultSyncValue,
      data: { ...defaultSyncValue.data, courses: [{ id: 'c1', stepik_course_id: 101, title: 'Python' }] },
      selectedCourseIds: ['c1'],
      isFilterActive: true,
    };
    renderLayout(true, syncValue);
    const filterBtn = await screen.findByTitle(/Выбрано: 1 из 1/);
    expect(filterBtn.className).toContain('text-cyber-blue');
    expect(filterBtn.className).toContain('border-cyber-blue/40');
  });
});
