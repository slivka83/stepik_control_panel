import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { isCurrentMonth } from '../utils/isCurrentMonth'

describe('isCurrentMonth', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns true for current ISO month', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('2026-07')).toBe(true)
  })

  it('returns false for past ISO month', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('2026-06')).toBe(false)
  })

  it('returns false for future ISO month', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('2026-08')).toBe(false)
  })

  it('returns true for current Russian month format', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('Июль 2026')).toBe(true)
  })

  it('returns false for past Russian month format', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('Июнь 2026')).toBe(false)
  })

  it('returns false for empty string', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('')).toBe(false)
  })

  it('returns false for null', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth(null)).toBe(false)
  })

  it('returns false for undefined', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth(undefined)).toBe(false)
  })

  it('returns false for unrecognizable format', () => {
    vi.setSystemTime(new Date('2026-07-15'))
    expect(isCurrentMonth('not-a-date')).toBe(false)
  })

  it('works at year boundary', () => {
    vi.setSystemTime(new Date('2027-01-01'))
    expect(isCurrentMonth('2027-01')).toBe(true)
    expect(isCurrentMonth('2026-12')).toBe(false)
  })

  it('works at month boundary', () => {
    vi.setSystemTime(new Date('2026-06-01'))
    expect(isCurrentMonth('2026-06')).toBe(true)
    expect(isCurrentMonth('2026-05')).toBe(false)
  })
})
