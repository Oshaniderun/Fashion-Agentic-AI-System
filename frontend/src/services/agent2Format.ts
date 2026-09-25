// Pure display/validation helpers for Agent 2 UI. No React, no I/O — unit-testable.
import type { RetrievalStatus } from '../types/agent2';

export const MIN_TOP_K = 1;
export const MAX_TOP_K = 20;

/** Validate the search form the same way the backend does (400 on violation). */
export function validateSearchForm(input: {
  max_price: number | null;
  top_k: number | null;
  query_text?: string | null;
}): string | null {
  if (input.max_price === null || Number.isNaN(input.max_price) || input.max_price <= 0) {
    return 'Price ceiling must be greater than 0.';
  }
  if (
    input.top_k === null ||
    Number.isNaN(input.top_k) ||
    !Number.isInteger(input.top_k) ||
    input.top_k < MIN_TOP_K ||
    input.top_k > MAX_TOP_K
  ) {
    return `top_k must be a whole number between ${MIN_TOP_K} and ${MAX_TOP_K}.`;
  }
  if (input.query_text && input.query_text.length > 2000) {
    return 'Query text exceeds the 2000 character limit.';
  }
  return null;
}

/**
 * Format a price honestly. Null/undefined/NaN → null (caller renders
 * "not listed"); never coerces missing data to 0 or a currency string.
 */
export function formatPrice(price?: number | null, currency?: string | null): string | null {
  if (price === null || price === undefined || Number.isNaN(price)) return null;
  const value = price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return currency ? `${currency} ${value}` : value;
}

/** 0..1 score → percent string for display. Never used to recompute relevance. */
export function formatScore(score?: number | null): string | null {
  if (score === null || score === undefined || Number.isNaN(score)) return null;
  return `${Math.round(score * 100)}%`;
}

/**
 * Honest null rendering: empty, "nan" and "unknown" strings collapse to null
 * so callers show a consistent "not listed" marker instead of fake values.
 */
export function cleanText(value?: string | null): string | null {
  if (value === null || value === undefined) return null;
  const t = value.trim();
  if (t === '' || t.toLowerCase() === 'nan' || t.toLowerCase() === 'none' || t.toLowerCase() === 'null') {
    return null;
  }
  return t;
}

export interface StatusMeta {
  label: string;
  badgeClass: string;
  message: string;
}

/** Maps Agent 2 retrieval status → badge class and user-facing meaning. */
export function statusMeta(status: RetrievalStatus, relaxed: string[] = []): StatusMeta {
  switch (status) {
    case 'ok':
      return { label: 'ok', badgeClass: 'badge badge-ok', message: 'Matches found within all constraints.' };
    case 'relaxed':
      return {
        label: 'relaxed',
        badgeClass: 'badge badge-warn',
        message: relaxed.length
          ? `Matches found after relaxing: ${relaxed.join(', ')}.`
          : 'Matches found after relaxing some constraints.',
      };
    case 'low_confidence':
      return {
        label: 'low confidence',
        badgeClass: 'badge badge-warn',
        message: 'Best-effort matches only — constraints were substantially loosened.',
      };
    case 'no_results':
      return { label: 'no results', badgeClass: 'badge badge-danger', message: 'No products found, even after the full relaxation ladder.' };
  }
}

/** Map an HTTP status to a safe, non-leaking user message (spec: no internals). */
export function describeHttpError(status?: number): string {
  switch (status) {
    case 400:
      return 'The search request was rejected — check the price ceiling and result count.';
    case 401:
      return 'Your session is no longer valid. Please sign in again.';
    case 404:
      return 'Product not found.';
    case 422:
      return 'The form values were not accepted. Price must be above 0 and result count between 1 and 20.';
    case 500:
      return 'The retrieval service hit an unexpected error. Please try again shortly.';
    default:
      return 'Could not reach the retrieval service.';
  }
}
