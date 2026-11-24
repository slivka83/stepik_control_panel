import { describe, it, expect } from 'vitest';
import { chartCommission, commissionWarning, formatUtmTooltip, paymentCommission } from '../utils/financials';

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

  it('does not calculate a commission for refunded payments', () => {
    // Regression: полный возврат давал «комиссию 100%» — в таблице теперь «—».
    expect(paymentCommission({ status: 'refunded', payment_amount: 1000, amount: -900 })).toBeNull();
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

  it('never returns a negative commission (refunds can make income > turnover)', () => {
    expect(chartCommission({ turnover: 100, income: 200 })).toBe(0);
  });
});

describe('commissionWarning', () => {
  it('does not flag the author-link rate of 7%', () => {
    expect(
      commissionWarning({
        payment_amount: 1000,
        amount: 930,
        status: 'debited',
        channel: 'А-ссылка',
      }),
    ).toBeNull();
  });

  it('does not flag a regular Stepik sale at 40% without an author link', () => {
    expect(commissionWarning({ payment_amount: 4900, amount: 2940, status: 'debited', channel: 'Stepik' })).toBeNull();
  });

  it('does not flag an author promo without an author link', () => {
    expect(
      commissionWarning({
        payment_amount: 4900,
        amount: 2940,
        status: 'debited',
        channel: 'Stepik',
        promo_is_author: true,
      }),
    ).toBeNull();
  });

  it('marks a high commission on an author-link payment as an error', () => {
    expect(commissionWarning({ payment_amount: 4900, amount: 2940, status: 'debited', channel: 'А-ссылка' })).toEqual({
      pct: 40,
      amount: 1960,
      expectedPct: 7,
      delta: 33,
      severity: 'error',
    });
    expect(
      commissionWarning({
        payment_amount: 4900,
        amount: 2940,
        status: 'debited',
        raw: { is_z_link_used: true },
      }),
    ).toMatchObject({ pct: 40, severity: 'error' });
  });

  it('does not flag a Stepik promo even on an author-link payment', () => {
    expect(
      commissionWarning({
        payment_amount: 4900,
        amount: 2940,
        status: 'debited',
        channel: 'А-ссылка',
        promo_is_stepik: true,
      }),
    ).toBeNull();
  });

  it('does not flag an unknown promo code (not synced)', () => {
    expect(
      commissionWarning({
        payment_amount: 4900,
        amount: 2940,
        status: 'debited',
        channel: 'А-ссылка',
        promo_code: 'MYSTERY',
        promo_is_stepik: null,
      }),
    ).toBeNull();
  });

  it('does not flag refunded payments', () => {
    expect(
      commissionWarning({ payment_amount: 7000, amount: -500, status: 'refunded', channel: 'А-ссылка' }),
    ).toBeNull();
  });

  it('does not flag a commission below the expected rate', () => {
    expect(
      commissionWarning({
        payment_amount: 1000,
        amount: 950,
        status: 'debited',
        channel: 'А-ссылка',
      }),
    ).toBeNull();
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
