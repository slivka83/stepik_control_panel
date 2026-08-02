import { describe, it, expect } from 'vitest';
import { formatNumber, formatCurrency } from '../utils/formatNumber';

describe('formatNumber', () => {
  it('formats positive integer', () => {
    const result = formatNumber(1500);
    expect(result).toBe('1\u00a0500');
  });

  it('formats zero', () => {
    expect(formatNumber(0)).toBe('0');
  });

  it('formats null as 0', () => {
    expect(formatNumber(null)).toBe('0');
  });

  it('formats undefined as 0', () => {
    expect(formatNumber(undefined)).toBe('0');
  });

  it('formats large numbers with separators', () => {
    expect(formatNumber(1000000)).toBe('1\u00a0000\u00a0000');
  });

  it('accepts additional options', () => {
    const result = formatNumber(1234.56, { maximumFractionDigits: 2 });
    expect(result).toBe('1\u00a0234,56');
  });
});

describe('formatCurrency', () => {
  it('formats with RUB currency', () => {
    const result = formatCurrency(50000);
    expect(result).toContain('50');
    expect(result).toContain('000');
  });

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('0\u00a0\u20bd');
  });

  it('formats null as 0', () => {
    expect(formatCurrency(null)).toBe('0\u00a0\u20bd');
  });

  it('formats with USD currency', () => {
    const result = formatCurrency(100, 'USD');
    expect(result).toContain('100');
    expect(result).toContain('$');
  });

  it('formats negative values', () => {
    const result = formatCurrency(-500);
    expect(result).toContain('500');
  });
});
