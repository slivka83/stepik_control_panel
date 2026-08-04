import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { SyncProvider, useSync } from '../contexts/SyncContext';
import { AuthProvider } from '../contexts/AuthContext';

const mockApiInstance = vi.hoisted(() => ({
  get: vi.fn(),
  interceptors: { response: { use: vi.fn() } },
}));

vi.mock('../api', () => ({
  default: mockApiInstance,
}));

function TestConsumer() {
  const sync = useSync();
  return (
    <div>
      <div data-testid="loading">{String(sync.loading)}</div>
      <div data-testid="error">{sync.error || 'no-error'}</div>
      <div data-testid="data-kpi">{sync.data.kpi ? 'loaded' : 'null'}</div>
    </div>
  );
}

function StatusConsumer() {
  const sync = useSync();
  return (
    <div>
      <div data-testid="status-progress">{sync.syncStatus.progress ?? 'none'}</div>
      <div data-testid="status-step">{sync.syncStatus.step || 'none'}</div>
    </div>
  );
}

function statusCallsCount() {
  return mockApiInstance.get.mock.calls.filter((call) => call[0] === '/sync/status').length;
}

function kpiCalls() {
  return mockApiInstance.get.mock.calls.filter((call) => call[0] === '/dashboard/kpi');
}

function FilterConsumer() {
  const sync = useSync();
  return (
    <div>
      <div data-testid="filter-active">{String(sync.isFilterActive)}</div>
      <div data-testid="filter-count">{sync.selectedCourseIds ? sync.selectedCourseIds.length : 'all'}</div>
      <div data-testid="courses-count">{(sync.data.courses || []).length}</div>
      <button onClick={() => sync.toggleCourse('c1')}>toggle-c1</button>
      <button onClick={() => sync.toggleCourse('c2')}>toggle-c2</button>
      <button onClick={() => sync.selectAllCourses()}>all</button>
      <button onClick={() => sync.selectNoneCourses()}>none</button>
    </div>
  );
}

describe('SyncContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      json: () => Promise.resolve({ id: 1, email: 'test@test.com' }),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders without crashing', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} });

    render(
      <AuthProvider>
        <SyncProvider>
          <div data-testid="mounted">mounted</div>
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('mounted')).toBeInTheDocument();
    });
  });

  it('calls api.get for endpoints when authenticated', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} });

    render(
      <AuthProvider>
        <SyncProvider>
          <div data-testid="mounted">mounted</div>
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(mockApiInstance.get).toHaveBeenCalledWith('/dashboard/kpi', expect.any(Object));
    });
  });

  it('sets loading to false after auth resolves', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} });

    render(
      <AuthProvider>
        <SyncProvider>
          <TestConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false');
    });
  });

  it('sets error when data fetch fails', async () => {
    mockApiInstance.get.mockRejectedValue(new Error('fetch failed'));

    render(
      <AuthProvider>
        <SyncProvider>
          <TestConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('error').textContent).not.toBe('no-error');
    });
  });

  it('sets data.kpi when kpi endpoint succeeds', async () => {
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/dashboard/kpi') return Promise.resolve({ data: { total_revenue: 100 } });
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <SyncProvider>
          <TestConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('data-kpi').textContent).toBe('loaded');
    });
  });

  it('exposes in-progress sync progress and step from status endpoint', async () => {
    vi.useFakeTimers();
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/sync/status') {
        return Promise.resolve({
          data: { in_progress: true, progress: 42, step: 'решения: загрузка', last_sync: null },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <SyncProvider>
          <StatusConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(30000);
    expect(screen.getByTestId('status-progress').textContent).toBe('42');
    expect(screen.getByTestId('status-step').textContent).toBe('решения: загрузка');
  });

  it('polls sync status every 2s while sync is in progress', async () => {
    vi.useFakeTimers();
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/sync/status') {
        return Promise.resolve({ data: { in_progress: true, progress: 10, step: 'курсы', last_sync: null } });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <SyncProvider>
          <div data-testid="mounted">mounted</div>
        </SyncProvider>
      </AuthProvider>,
    );

    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(0);
    expect(statusCallsCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(4000);
    expect(statusCallsCount()).toBe(3);
  });

  it('does not send course_ids when no filter is active', async () => {
    mockApiInstance.get.mockResolvedValue({ data: {} });

    render(
      <AuthProvider>
        <SyncProvider>
          <div data-testid="mounted">mounted</div>
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(kpiCalls().length).toBeGreaterThan(0);
    });
    expect(kpiCalls()[0][1].params).toBeUndefined();
  });

  it('sends course_ids to filterable endpoints after toggling a course', async () => {
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/courses') {
        return Promise.resolve({
          data: { courses: [{ id: 'c1', title: 'A' }, { id: 'c2', title: 'B' }] },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <SyncProvider>
          <FilterConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('filter-active').textContent).toBe('false');
      expect(screen.getByTestId('courses-count').textContent).toBe('2');
    });

    fireEvent.click(screen.getByText('toggle-c1'));

    await waitFor(() => {
      expect(screen.getByTestId('filter-active').textContent).toBe('true');
    });
    expect(screen.getByTestId('filter-count').textContent).toBe('1');
    const calls = kpiCalls();
    const filtered = calls.find((call) => call[1].params && call[1].params.course_ids);
    expect(filtered).toBeDefined();
    expect(filtered[1].params.course_ids).toBe('c2');
    expect(mockApiInstance.get).toHaveBeenCalledWith('/courses', expect.not.objectContaining({ params: { course_ids: 'c2' } }));
  });

  it('returns to all-courses mode via selectAllCourses (no course_ids)', async () => {
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/courses') {
        return Promise.resolve({
          data: { courses: [{ id: 'c1', title: 'A' }, { id: 'c2', title: 'B' }] },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <SyncProvider>
          <FilterConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('filter-active').textContent).toBe('false');
      expect(screen.getByTestId('courses-count').textContent).toBe('2');
    });

    fireEvent.click(screen.getByText('toggle-c1'));
    await waitFor(() => {
      expect(screen.getByTestId('filter-count').textContent).toBe('1');
    });

    fireEvent.click(screen.getByText('all'));
    await waitFor(() => {
      expect(screen.getByTestId('filter-active').textContent).toBe('false');
    });
    const last = kpiCalls().pop();
    expect(last[1].params).toBeUndefined();
  });

  it('sends an empty course_ids when nothing is selected (selectNoneCourses)', async () => {
    mockApiInstance.get.mockImplementation((url) => {
      if (url === '/courses') {
        return Promise.resolve({
          data: { courses: [{ id: 'c1', title: 'A' }, { id: 'c2', title: 'B' }] },
        });
      }
      return Promise.resolve({ data: {} });
    });

    render(
      <AuthProvider>
        <SyncProvider>
          <FilterConsumer />
        </SyncProvider>
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId('courses-count').textContent).toBe('2');
    });

    fireEvent.click(screen.getByText('toggle-c1'));
    await waitFor(() => {
      expect(screen.getByTestId('filter-count').textContent).toBe('1');
    });

    fireEvent.click(screen.getByText('toggle-c2'));
    await waitFor(() => {
      expect(screen.getByTestId('filter-count').textContent).toBe('0');
    });
    const last = kpiCalls().pop();
    expect(last[1].params).toEqual({ course_ids: '' });
  });
});
