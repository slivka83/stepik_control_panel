import { describe, it, expect } from 'vitest';
import {
  CHART_COLORS,
  APP_VERSION,
  COHORT_COLORS,
  COHORT_LABELS,
  COHORT_DAYS,
  STATUS_LABELS,
  STATUS_COLORS,
  NAV_GROUPS,
} from '../constants.jsx';

describe('Constants', () => {
  describe('CHART_COLORS', () => {
    it('has all chart color keys', () => {
      expect(CHART_COLORS).toHaveProperty('cyberBlue');
      expect(CHART_COLORS).toHaveProperty('neonGreen');
      expect(CHART_COLORS).toHaveProperty('gridLine');
      expect(CHART_COLORS).toHaveProperty('textSecondary');
      expect(CHART_COLORS).toHaveProperty('panelBg');
    });

    it('all values are valid hex colors', () => {
      for (const val of Object.values(CHART_COLORS)) {
        expect(val).toMatch(/^#[0-9a-f]{6}$/i);
      }
    });
  });

  describe('APP_VERSION', () => {
    it('is a semver string', () => {
      expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
    });

    it('is version 0.2.0', () => {
      expect(APP_VERSION).toBe('0.2.0');
    });
  });

  describe('COHORT_COLORS', () => {
    it('has all four cohort types', () => {
      expect(COHORT_COLORS).toHaveProperty('active');
      expect(COHORT_COLORS).toHaveProperty('passive');
      expect(COHORT_COLORS).toHaveProperty('fading');
      expect(COHORT_COLORS).toHaveProperty('sleeping');
    });

    it('each color has text, bg, and hex', () => {
      for (const color of Object.values(COHORT_COLORS)) {
        expect(color).toHaveProperty('text');
        expect(color).toHaveProperty('bg');
        expect(color).toHaveProperty('hex');
        expect(color.hex).toMatch(/^#[0-9a-f]{6}$/);
      }
    });
  });

  describe('COHORT_LABELS', () => {
    it('has Russian labels for all cohorts', () => {
      expect(COHORT_LABELS.active).toBe('Активные');
      expect(COHORT_LABELS.passive).toBe('Пассивные');
      expect(COHORT_LABELS.fading).toBe('Затухающие');
      expect(COHORT_LABELS.sleeping).toBe('Спящие');
    });
  });

  describe('COHORT_DAYS', () => {
    it('has day ranges for all cohorts', () => {
      expect(COHORT_DAYS.active).toContain('7');
      expect(COHORT_DAYS.passive).toContain('30');
      expect(COHORT_DAYS.fading).toContain('90');
      expect(COHORT_DAYS.sleeping).toContain('90');
    });
  });

  describe('STATUS_LABELS', () => {
    it('has Russian labels for all statuses', () => {
      expect(STATUS_LABELS.debited).toBe('Зачислен');
      expect(STATUS_LABELS.refunded).toBe('Возврат');
      expect(STATUS_LABELS.pending).toBe('Ожидание');
    });
  });

  describe('STATUS_COLORS', () => {
    it('has color classes for all statuses', () => {
      expect(STATUS_COLORS.debited).toContain('neon-green');
      expect(STATUS_COLORS.refunded).toContain('crimson-alert');
      expect(STATUS_COLORS.pending).toContain('amber-alert');
    });
  });

  describe('NAV_GROUPS', () => {
    it('has three navigation groups', () => {
      expect(NAV_GROUPS).toHaveLength(3);
    });

    it('has nine navigation items in total', () => {
      const items = NAV_GROUPS.flatMap((group) => group.items);
      expect(items).toHaveLength(9);
    });

    it('each item has to, label, and icon', () => {
      for (const group of NAV_GROUPS) {
        for (const item of group.items) {
          expect(item).toHaveProperty('to');
          expect(item).toHaveProperty('label');
          expect(item).toHaveProperty('icon');
        }
      }
    });

    it('groups items in the expected order', () => {
      const labelsByGroup = NAV_GROUPS.map((group) => group.items.map((item) => item.label));
      expect(labelsByGroup).toEqual([
        ['Дашборд', 'Активности', 'Курсы'],
        ['Финансы', 'Решения', 'Комментарии', 'Сертификаты', 'Отзывы'],
        ['Студенты'],
      ]);
    });

    it('first group starts with dashboard', () => {
      expect(NAV_GROUPS[0].items[0].to).toBe('/');
      expect(NAV_GROUPS[0].items[0].label).toBe('Дашборд');
    });

    it('students group comes last', () => {
      expect(NAV_GROUPS[2].items[0].to).toBe('/students');
      expect(NAV_GROUPS[2].items[0].label).toBe('Студенты');
    });

    it('certificates item comes after comments', () => {
      const items = NAV_GROUPS[1].items;
      expect(items[2].to).toBe('/comments');
      expect(items[3].to).toBe('/certificates');
      expect(items[3].label).toBe('Сертификаты');
    });

    it('reviews item comes after certificates', () => {
      const items = NAV_GROUPS[1].items;
      expect(items[4].to).toBe('/reviews');
      expect(items[4].label).toBe('Отзывы');
    });
  });
});
