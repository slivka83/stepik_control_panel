import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useServerTable } from '../hooks/useServerTable';
import { SyncContext } from '../contexts/SyncContext';
import api from '../api';

vi.mock('../api', () => ({
  default: { get: vi.fn() },
}));

const COLUMNS = [
  { key: 'name', numeric: false },
  { key: 'total', numeric: true },
];

const INITIAL_SORT = { key: 'name', dir: 'asc' };

function wrapperWith(syncValue) {
  return function Wrapper({ children }) {
    return <SyncContext.Provider value={syncValue}>{children}</SyncContext.Provider>;
  };
}

const baseSync = (extra = {}) => ({
  syncStatus: { in_progress: false, last_sync: null },
  selectedCourseIds: null,
  ...extra,
});

describe('useServerTable', () => {
  beforeEach(() => {
    api.get.mockReset();
    api.get.mockResolvedValue({ data: { rows: [], total: 0 } });
  });

  it('fetches the first page with sort and paging params', async () => {
    const { result } = renderHook(
      () =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
        }),
      { wrapper: wrapperWith(baseSync()) },
    );

    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(api.get).toHaveBeenLastCalledWith('/test', {
      params: expect.objectContaining({ skip: 0, sort: 'name', order: 'asc' }),
    });
    expect(result.current.rows).toEqual([]);
  });

  it('passes the course filter and extra params', async () => {
    renderHook(
      () =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
          extraParams: { type: 'unanswered' },
        }),
      { wrapper: wrapperWith(baseSync({ selectedCourseIds: ['u1', 'u2'] })) },
    );

    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(api.get.mock.calls[0][1].params).toMatchObject({
      type: 'unanswered',
      course_ids: 'u1,u2',
    });
  });

  it('does not fetch while disabled and fetches when enabled', async () => {
    const { rerender } = renderHook(
      ({ enabled }) =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
          enabled,
        }),
      { wrapper: wrapperWith(baseSync()), initialProps: { enabled: false } },
    );

    await act(async () => {});
    expect(api.get).not.toHaveBeenCalled();

    rerender({ enabled: true });
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
  });

  it('refetches the current page after a new sync', async () => {
    let setSyncValue;
    function Wrapper({ children }) {
      const [value, setValue] = useState(baseSync({ syncStatus: { in_progress: false, last_sync: '2026-07-01T00:00:00' } }));
      setSyncValue = setValue;
      return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
    }
    renderHook(
      () =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));

    act(() => setSyncValue(baseSync({ syncStatus: { in_progress: false, last_sync: '2026-08-01T00:00:00' } })));
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  });

  it('refetches on sync with resetPageOnSync even when already on page 1', async () => {
    // Regression: setPage(1) на первой странице — no-op, и список не обновлялся.
    let setSyncValue;
    function Wrapper({ children }) {
      const [value, setValue] = useState(
        baseSync({ syncStatus: { in_progress: false, last_sync: '2026-07-01T00:00:00' } }),
      );
      setSyncValue = setValue;
      return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
    }
    renderHook(
      () =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
          resetPageOnSync: true,
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));

    act(() =>
      setSyncValue(baseSync({ syncStatus: { in_progress: false, last_sync: '2026-08-01T00:00:00' } })),
    );
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  });

  it('refetches when the first-ever sync sets last_sync (null → timestamp)', async () => {
    let setSyncValue;
    function Wrapper({ children }) {
      const [value, setValue] = useState(baseSync());
      setSyncValue = setValue;
      return <SyncContext.Provider value={value}>{children}</SyncContext.Provider>;
    }
    renderHook(
      () =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
        }),
      { wrapper: Wrapper },
    );

    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    act(() =>
      setSyncValue(baseSync({ syncStatus: { in_progress: false, last_sync: '2026-08-01T00:00:00' } })),
    );
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));
  });

  it('returns to page 1 when the reset key changes', async () => {
    api.get.mockResolvedValue({ data: { rows: [], total: 40 } });
    const { result, rerender } = renderHook(
      ({ resetKey }) =>
        useServerTable({
          endpoint: '/test',
          columns: COLUMNS,
          initialSort: INITIAL_SORT,
          resultKey: 'rows',
          resetKey,
        }),
      { wrapper: wrapperWith(baseSync()), initialProps: { resetKey: 'a' } },
    );

    await waitFor(() => expect(api.get).toHaveBeenCalled());
    act(() => result.current.setPage(2));
    await waitFor(() =>
      expect(api.get).toHaveBeenLastCalledWith('/test', {
        params: expect.objectContaining({ skip: 10 }),
      }),
    );

    rerender({ resetKey: 'b' });
    await waitFor(() =>
      expect(api.get).toHaveBeenLastCalledWith('/test', {
        params: expect.objectContaining({ skip: 0 }),
      }),
    );
  });
});
