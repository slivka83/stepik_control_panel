import { describe, it, expect } from 'vitest';
import { chartCommission, formatUtmTooltip, paymentCommission } from '../utils/financials';

describe('paymentCommission', () => {
  it('counts the Stepik fee as the difference between payment and income', () => {
    expect(paymentCommission({ payment_amount: 1000, amount: 850 })).toEqual({ pct: 15, amount: 150 });
  });

  it('rounds the percentage to whole numbers', () => {
    expect(paymentCommission({ payment_amount: 3000, amount: 2100 }).pct).toBe(30);
  });

  it('returns null when there is no payment to take a fee from', () => {
    expect(paymentCommission({ payment_amount: 0, amount: 0 })).toBeNull();
    expect(paymentCommission({})).toBeNull();
  });

  it('handles refunded payments (negative amount) without a negative fee', () => {
    expect(paymentCommission({ payment_amount: 1000, amount: -900 })).toEqual({ pct: 10, amount: 100 });
  });

  it('never reports a negative fee when income exceeds the payment', () => {
    expect(paymentCommission({ payment_amount: 1000, amount: 1200 })).toEqual({ pct: 0, amount: 0 });
  });
});

describe('chartCommission', () => {
  it('is the money difference between turnover and income', () => {
    expect(chartCommission({ turnover: 1000, income: 800 })).toBe(200);
  });

  it('is zero for an empty row', () => {
    expect(chartCommission({})).toBe(0);
    expect(chartCommission(null)).toBe(0);
  });
});

describe('formatUtmTooltip', () => {
  it('renders one label per line', () => {
    const raw = { last_course_click_utm: { utm_source: 'yandex_stpk', utm_campaign: 'spring' } };
    expect(formatUtmTooltip(raw)).toBe('utm_source: yandex_stpk\nutm_campaign: spring');
  });

  it('renders empty values as blank instead of null', () => {
    expect(formatUtmTooltip({ last_course_click_utm: { utm_term: null } })).toBe('utm_term: ');
  });

  it('returns an empty string when there are no UTM marks', () => {
    expect(formatUtmTooltip({})).toBe('');
    expect(formatUtmTooltip(null)).toBe('');
    expect(formatUtmTooltip({ last_course_click_utm: 'oops' })).toBe('');
  });
});
