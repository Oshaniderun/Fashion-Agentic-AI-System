// Pure display helpers for the budget & purchase-planning UI. No React, no
// I/O — unit-testable. Money values come from the backend already computed;
// this module only formats them and never recomputes totals.
import type { BudgetStatus } from '../types/budget';

/** Format a USD amount honestly. Null/NaN → null (caller renders a marker). */
export function formatUsd(value?: number | null): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return `USD ${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export interface BudgetStatusMeta {
  label: string;
  badgeClass: string;
  message: string;
}

/** Maps a budget status → badge class and a short, honest user-facing meaning. */
export function budgetStatusMeta(
  status: BudgetStatus,
  opts: { buyNothingAvailable?: boolean } = {}
): BudgetStatusMeta {
  switch (status) {
    case 'within_budget':
      return {
        label: 'within budget',
        badgeClass: 'badge badge-ok',
        message: 'At least one new-product combination fits your budget.',
      };
    case 'no_purchase_needed':
      return {
        label: 'no purchase needed',
        badgeClass: 'badge badge-ok',
        message: 'Your existing wardrobe already covers every requirement.',
      };
    case 'partially_feasible':
      return {
        label: 'partially feasible',
        badgeClass: 'badge badge-warn',
        message: opts.buyNothingAvailable
          ? 'Full new-product sets exceed your budget, but a zero-purchase wardrobe option is available.'
          : 'Only some of the required pieces fit within your budget.',
      };
    case 'exceeds_budget':
      return {
        label: 'over budget',
        badgeClass: 'badge badge-danger',
        message: 'Every candidate combination exceeds your budget ceiling.',
      };
  }
}

/**
 * Catalogue ids are Amazon ASINs, but the dataset's url column is empty for
 * every row, so the store link is derived from the ASIN itself.
 */
export function storeUrl(productId: string, listed?: string | null): string | null {
  if (listed) return listed;
  return /^[A-Z0-9]{10}$/.test(productId) ? `https://www.amazon.com/dp/${productId}` : null;
}

/**
 * Decision scores and weights travel from Agent 4 as 0-1 decimals. This turns
 * one into a percentage string for reading; it clamps exactly like the score
 * bar does, so the number beside a bar always matches the bar's fill.
 */
export function formatScorePercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
}

export const STRATEGY_LABELS: Record<string, string> = {
  buy_nothing: 'Buy nothing',
  best_value: 'Best value',
  top_match: 'Top match',
  minimal_purchase: 'Minimal purchase',
  all: 'All strategies',
};

export function strategyLabel(strategy?: string | null): string {
  if (!strategy) return '—';
  return STRATEGY_LABELS[strategy] ?? strategy.replace(/_/g, ' ');
}
