import { describe, it, expect } from 'vitest';
import { mergePublishedIntoSubmissions } from '../utils/mergePublished';

describe('mergePublishedIntoSubmissions', () => {
  it('adds published per month by label', () => {
    const subs = { months: [{ month: 'Январь 2026', total: 100, correct: 80 }], by_course: [] };
    const pub = {
      months: [
        { month: 'Январь 2026', dark: 12, light: 12 },
        { month: 'Февраль 2026', dark: 5, light: 5 },
      ],
    };
    const out = mergePublishedIntoSubmissions(subs, pub);
    expect(out.months[0].published).toBe(12);
  });

  it('defaults to 0 for months without published data', () => {
    const subs = { months: [{ month: 'Февраль 2026', total: 10, correct: 5 }] };
    const out = mergePublishedIntoSubmissions(subs, { months: [] });
    expect(out.months[0].published).toBe(0);
  });

  it('keeps other submission keys intact', () => {
    const subs = {
      months: [{ month: 'Январь 2026', total: 100, correct: 80, students: 42 }],
      by_course: [{ title: 'X' }],
      years: [],
    };
    const out = mergePublishedIntoSubmissions(subs, { months: [] });
    expect(out.by_course).toEqual([{ title: 'X' }]);
    expect(out.years).toEqual([]);
    expect(out.months[0].students).toBe(42);
    expect(out.months[0].total).toBe(100);
  });

  it('returns null when submissions is null', () => {
    expect(mergePublishedIntoSubmissions(null, { months: [] })).toBeNull();
  });

  it('handles missing publishedSolutions', () => {
    const subs = { months: [{ month: 'Март 2026', total: 1, correct: 1 }] };
    const out = mergePublishedIntoSubmissions(subs, null);
    expect(out.months[0].published).toBe(0);
  });
});
