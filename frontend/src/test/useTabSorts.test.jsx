import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useTabSorts } from '../hooks/useTabSorts';

const COLUMNS = {
  months: [
    { key: 'month', numeric: true },
    { key: 'students', numeric: true },
    { key: 'title' },
  ],
  courses: [{ key: 'title' }, { key: 'total', numeric: true }],
};

const INITIAL = {
  months: { key: 'month', dir: 'desc' },
  courses: { key: 'title', dir: 'asc' },
};

describe('useTabSorts', () => {
  it('returns the initial sort of every tab', () => {
    const { result } = renderHook(() => useTabSorts(COLUMNS, INITIAL));

    expect(result.current.sorts).toEqual(INITIAL);
  });

  it('sorts a new numeric column descending', () => {
    const { result } = renderHook(() => useTabSorts(COLUMNS, INITIAL));

    act(() => result.current.onSort('months')('students'));

    expect(result.current.sorts.months).toEqual({ key: 'students', dir: 'desc' });
  });

  it('sorts a new text column ascending', () => {
    const { result } = renderHook(() => useTabSorts(COLUMNS, INITIAL));

    act(() => result.current.onSort('months')('title'));

    expect(result.current.sorts.months).toEqual({ key: 'title', dir: 'asc' });
  });

  it('toggles the direction of the active column', () => {
    const { result } = renderHook(() => useTabSorts(COLUMNS, INITIAL));

    act(() => result.current.onSort('months')('month'));
    expect(result.current.sorts.months).toEqual({ key: 'month', dir: 'asc' });

    act(() => result.current.onSort('months')('month'));
    expect(result.current.sorts.months).toEqual({ key: 'month', dir: 'desc' });
  });

  it('keeps tabs independent', () => {
    const { result } = renderHook(() => useTabSorts(COLUMNS, INITIAL));

    act(() => result.current.onSort('months')('students'));

    expect(result.current.sorts.months).toEqual({ key: 'students', dir: 'desc' });
    expect(result.current.sorts.courses).toEqual({ key: 'title', dir: 'asc' });
  });

  it('falls back to ascending for an unknown column config', () => {
    const { result } = renderHook(() => useTabSorts(COLUMNS, INITIAL));

    act(() => result.current.onSort('months')('missing'));

    expect(result.current.sorts.months).toEqual({ key: 'missing', dir: 'asc' });
  });
});
