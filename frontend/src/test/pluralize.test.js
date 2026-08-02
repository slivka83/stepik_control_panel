import { describe, it, expect } from 'vitest';
import { pluralize } from '../utils/pluralize';

describe('pluralize', () => {
  const forms = ['студент', 'студента', 'студентов'];

  it('returns form 0 for 1', () => {
    expect(pluralize(1, forms)).toBe('студент');
  });

  it('returns form 0 for 21', () => {
    expect(pluralize(21, forms)).toBe('студент');
  });

  it('returns form 1 for 2', () => {
    expect(pluralize(2, forms)).toBe('студента');
  });

  it('returns form 1 for 3', () => {
    expect(pluralize(3, forms)).toBe('студента');
  });

  it('returns form 1 for 4', () => {
    expect(pluralize(4, forms)).toBe('студента');
  });

  it('returns form 2 for 5', () => {
    expect(pluralize(5, forms)).toBe('студентов');
  });

  it('returns form 2 for 10', () => {
    expect(pluralize(10, forms)).toBe('студентов');
  });

  it('returns form 2 for 11', () => {
    expect(pluralize(11, forms)).toBe('студентов');
  });

  it('returns form 1 for 12', () => {
    expect(pluralize(12, forms)).toBe('студентов');
  });

  it('returns form 1 for 22', () => {
    expect(pluralize(22, forms)).toBe('студента');
  });

  it('returns form 0 for 101', () => {
    expect(pluralize(101, forms)).toBe('студент');
  });

  it('returns form 2 for 0', () => {
    expect(pluralize(0, forms)).toBe('студентов');
  });

  it('returns form 2 for 100', () => {
    expect(pluralize(100, forms)).toBe('студентов');
  });
});
