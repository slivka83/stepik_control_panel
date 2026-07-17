import { describe, it, expect } from 'vitest'
import {
  COHORT_COLORS,
  COHORT_LABELS,
  COHORT_DAYS,
  STATUS_LABELS,
  STATUS_COLORS,
  NAV_ITEMS,
} from '../constants'

describe('Constants', () => {
  describe('COHORT_COLORS', () => {
    it('has all four cohort types', () => {
      expect(COHORT_COLORS).toHaveProperty('active')
      expect(COHORT_COLORS).toHaveProperty('passive')
      expect(COHORT_COLORS).toHaveProperty('fading')
      expect(COHORT_COLORS).toHaveProperty('sleeping')
    })

    it('each color has text, bg, and hex', () => {
      for (const [key, color] of Object.entries(COHORT_COLORS)) {
        expect(color).toHaveProperty('text')
        expect(color).toHaveProperty('bg')
        expect(color).toHaveProperty('hex')
        expect(color.hex).toMatch(/^#[0-9a-f]{6}$/)
      }
    })
  })

  describe('COHORT_LABELS', () => {
    it('has Russian labels for all cohorts', () => {
      expect(COHORT_LABELS.active).toBe('Активные')
      expect(COHORT_LABELS.passive).toBe('Пассивные')
      expect(COHORT_LABELS.fading).toBe('Затухающие')
      expect(COHORT_LABELS.sleeping).toBe('Спящие')
    })
  })

  describe('COHORT_DAYS', () => {
    it('has day ranges for all cohorts', () => {
      expect(COHORT_DAYS.active).toContain('7')
      expect(COHORT_DAYS.passive).toContain('30')
      expect(COHORT_DAYS.fading).toContain('90')
      expect(COHORT_DAYS.sleeping).toContain('90')
    })
  })

  describe('STATUS_LABELS', () => {
    it('has Russian labels for all statuses', () => {
      expect(STATUS_LABELS.debited).toBe('Зачислен')
      expect(STATUS_LABELS.refunded).toBe('Возврат')
      expect(STATUS_LABELS.pending).toBe('Ожидание')
    })
  })

  describe('NAV_ITEMS', () => {
    it('has four navigation items', () => {
      expect(NAV_ITEMS).toHaveLength(4)
    })

    it('each item has to, label, and icon', () => {
      for (const item of NAV_ITEMS) {
        expect(item).toHaveProperty('to')
        expect(item).toHaveProperty('label')
        expect(item).toHaveProperty('icon')
      }
    })

    it('first item is dashboard', () => {
      expect(NAV_ITEMS[0].to).toBe('/')
      expect(NAV_ITEMS[0].label).toBe('Дашборд')
    })
  })
})
