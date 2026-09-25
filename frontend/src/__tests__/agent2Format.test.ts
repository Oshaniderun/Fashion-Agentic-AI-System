import { describe, it, expect } from 'vitest';
import {
  cleanText,
  describeHttpError,
  formatPrice,
  formatScore,
  statusMeta,
  validateSearchForm,
} from '../services/agent2Format';

describe('validateSearchForm', () => {
  it('accepts a valid request', () => {
    expect(validateSearchForm({ max_price: 50, top_k: 5 })).toBeNull();
  });
  it('rejects price <= 0 (matches backend gt=0)', () => {
    expect(validateSearchForm({ max_price: 0, top_k: 5 })).toMatch(/greater than 0/);
    expect(validateSearchForm({ max_price: -3, top_k: 5 })).toMatch(/greater than 0/);
    expect(validateSearchForm({ max_price: null, top_k: 5 })).toMatch(/greater than 0/);
  });
  it('rejects top_k outside 1..20 and non-integers', () => {
    expect(validateSearchForm({ max_price: 10, top_k: 0 })).toMatch(/between 1 and 20/);
    expect(validateSearchForm({ max_price: 10, top_k: 21 })).toMatch(/between 1 and 20/);
    expect(validateSearchForm({ max_price: 10, top_k: 4.5 })).toMatch(/whole number/);
  });
  it('rejects query_text over 2000 chars', () => {
    expect(validateSearchForm({ max_price: 10, top_k: 5, query_text: 'a'.repeat(2001) })).toMatch(/2000/);
  });
});

describe('formatPrice (honest nulls)', () => {
  it('returns null for missing/NaN, never 0', () => {
    expect(formatPrice(null, 'USD')).toBeNull();
    expect(formatPrice(undefined, 'USD')).toBeNull();
    expect(formatPrice(NaN, 'USD')).toBeNull();
  });
  it('formats a real price with currency', () => {
    expect(formatPrice(13.99, 'USD')).toBe('USD 13.99');
    expect(formatPrice(1234.5, 'USD')).toBe('USD 1,234.50');
  });
  it('formats a price without inventing a currency', () => {
    expect(formatPrice(20)).toBe('20.00');
  });
});

describe('formatScore', () => {
  it('renders 0..1 as percent and null as null', () => {
    expect(formatScore(0.923)).toBe('92%');
    expect(formatScore(1)).toBe('100%');
    expect(formatScore(0)).toBe('0%');
    expect(formatScore(null)).toBeNull();
  });
});

describe('cleanText', () => {
  it('collapses empty and pseudo-null tokens to null', () => {
    expect(cleanText('')).toBeNull();
    expect(cleanText('   ')).toBeNull();
    expect(cleanText('nan')).toBeNull();
    expect(cleanText('None')).toBeNull();
    expect(cleanText(null)).toBeNull();
  });
  it('keeps real values', () => {
    expect(cleanText('black')).toBe('black');
    expect(cleanText('Unknown')).toBe('Unknown');
  });
});

describe('statusMeta', () => {
  it('maps each retrieval status to a badge and message', () => {
    expect(statusMeta('ok').badgeClass).toContain('badge-ok');
    expect(statusMeta('relaxed', ['colour']).message).toContain('colour');
    expect(statusMeta('low_confidence').badgeClass).toContain('badge-warn');
    expect(statusMeta('no_results').badgeClass).toContain('badge-danger');
  });
});

describe('describeHttpError', () => {
  it('gives safe messages without leaking internals', () => {
    expect(describeHttpError(401)).toMatch(/sign in again/i);
    expect(describeHttpError(422)).toMatch(/Price must be above 0/);
    expect(describeHttpError(500)).not.toMatch(/traceback|stack/i);
  });
});
