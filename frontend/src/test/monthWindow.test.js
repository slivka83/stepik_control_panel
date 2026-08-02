import { describe, it, expect } from 'vitest';
import { buildMonthWindow, parseMonthLabel, formatMonthLabel } from '../utils/monthWindow.js';

const NOW = new Date(2026, 7, 15); // 15 августа 2026

describe('parseMonthLabel', () => {
  it('parses Russian month labels', () => {
    expect(parseMonthLabel('Август 2026')).toEqual({ year: 2026, month: 8 });
    expect(parseMonthLabel('Январь 2025')).toEqual({ year: 2025, month: 1 });
  });

  it('returns null for invalid labels', () => {
    expect(parseMonthLabel('2026-08-01T00:00:00')).toBeNull();
    expect(parseMonthLabel('foo')).toBeNull();
    expect(parseMonthLabel('')).toBeNull();
    expect(parseMonthLabel(null)).toBeNull();
  });
});

describe('formatMonthLabel', () => {
  it('formats month and year as Russian label', () => {
    expect(formatMonthLabel(8, 2026)).toBe('Август 2026');
    expect(formatMonthLabel(1, 2025)).toBe('Январь 2025');
  });
});

describe('buildMonthWindow', () => {
  it('returns 18 months ending with the current month', () => {
    const result = buildMonthWindow([{ month: 'Август 2026', income: 100 }], { now: NOW });
    expect(result).toHaveLength(18);
    expect(result[17]).toEqual({ month: 'Август 2026', income: 100 });
    expect(result[0].month).toBe('Март 2025');
  });

  it('fills gaps with zero months while preserving data months', () => {
    const result = buildMonthWindow(
      [
        { month: 'Январь 2026', income: 500 },
        { month: 'Март 2026', income: 300 },
      ],
      { now: NOW },
    );
    expect(result.find((m) => m.month === 'Январь 2026').income).toBe(500);
    expect(result.find((m) => m.month === 'Март 2026').income).toBe(300);
    expect(result.find((m) => m.month === 'Февраль 2026')).toEqual({ month: 'Февраль 2026' });
  });

  it('keeps months outside the window out of the result', () => {
    const result = buildMonthWindow([{ month: 'Февраль 2024', income: 999 }], { now: NOW });
    expect(result.some((m) => m.month === 'Февраль 2024')).toBe(false);
  });

  it('returns [] for empty input', () => {
    expect(buildMonthWindow([])).toEqual([]);
    expect(buildMonthWindow(null)).toEqual([]);
  });

  it('falls back to last N months when labels are not parseable', () => {
    const months = Array.from({ length: 25 }, (_, i) => ({ month: `Месяц ${i + 1}`, total: i }));
    const result = buildMonthWindow(months, { now: NOW });
    expect(result).toHaveLength(18);
    expect(result[17].month).toBe('Месяц 25');
  });
});
