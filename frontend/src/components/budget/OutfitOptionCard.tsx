import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ShoppingBag, Sparkles } from 'lucide-react';
import type {
  BudgetSource,
  BudgetStatus,
  CandidateProductItem,
  OutfitOption,
  RetrievalRetryLog,
} from '../../types/budget';
import { formatUsd, budgetStatusMeta, strategyLabel } from '../../services/budgetFormat';
import { trackProductClick } from '../../services/budgetService';
import { extractErrorMessage } from '../../services/api';

interface Props {
  requestId: string;
  userId?: number | null;
  option: OutfitOption;
  recommended: boolean;
}

/** One outfit option: cost breakdown, purchased products, reused wardrobe. */
export function OutfitOptionCard({ requestId, userId, option, recommended }: Props) {
  const [open, setOpen] = useState(false);
  const cb = option.cost_breakdown;

  const openTracked = async (p: CandidateProductItem) => {
    const target = p.url;
    try {
      await trackProductClick({
        product_id: p.product_id,
        product_name: p.name,
        product_url: target ?? null,
        store: p.store ?? null,
        category: p.category,
        price_usd: p.price ?? null,
        request_id: requestId,
        user_id: userId != null ? String(userId) : undefined,
      });
    } catch {
      /* tracking is best-effort; the user still gets their link */
    }
    if (target) {
      window.open(target, '_blank', 'noopener,noreferrer');
    }
  };

  return (
    <div className="panel stack">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0 }}>
            {option.name}{' '}
            {recommended && <span className="badge badge-ok">Recommended</span>}
            {option.strategy === 'buy_nothing' && (
              <span className="badge badge-muted" style={{ marginLeft: 6 }}>
                <Sparkles size={12} style={{ verticalAlign: -2 }} /> zero spend
              </span>
            )}
          </h3>
          <p className="meta" style={{ margin: '4px 0 0' }}>
            {strategyLabel(option.strategy)} · relevance {Math.round(option.relevance_score * 100)}% ·
            value {Math.round(option.overall_value_score * 100)}%
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <p style={{ margin: 0, fontWeight: 700 }}>{formatUsd(cb.total_cost) ?? '—'}</p>
          <p className="meta" style={{ margin: 0 }}>
            of {formatUsd(cb.budget_ceiling)}
          </p>
        </div>
      </div>

      <div className="chip-row">
        <span className={`badge ${option.is_within_budget ? 'badge-ok' : 'badge-danger'}`}>
          {option.is_within_budget ? 'within budget' : 'over budget'}
        </span>
        {cb.savings_amount > 0 && (
          <span className="badge badge-muted">
            saves {formatUsd(cb.savings_amount)} ({cb.savings_percentage.toFixed(0)}%)
          </span>
        )}
      </div>

      <p style={{ margin: 0 }} className="meta">
        {option.financial_explanation}
      </p>

      <button
        type="button"
        className="btn btn-ghost"
        style={{ alignSelf: 'flex-start' }}
        onClick={() => setOpen(!open)}
      >
        {open
          ? 'Hide items'
          : `Show items (${option.selected_products.length} to buy, ${option.wardrobe_items_used.length} owned)`}
      </button>

      {open && (
        <>
          {option.selected_products.length > 0 ? (
            <div className="stack">
              {option.selected_products.map((p) => (
                <div
                  key={p.product_id}
                  className="row"
                  style={{ justifyContent: 'space-between', alignItems: 'center', gap: 8 }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{p.name}</div>
                    <div className="meta">
                      {p.category}
                      {p.colour ? ` · ${p.colour}` : ''}
                      {p.store ? ` · ${p.store}` : ''}
                    </div>
                  </div>
                  <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                    <strong>{formatUsd(p.price) ?? 'not listed'}</strong>
                    <Link
                      className="btn btn-secondary"
                      to={{
                        pathname: `/agent2/products/${encodeURIComponent(p.product_id)}`,
                        search: `from=${encodeURIComponent(`/budget/${requestId}`)}`,
                      }}
                    >
                      Details
                    </Link>
                    {p.url && (
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => void openTracked(p)}
                      >
                        <ShoppingBag size={14} /> View
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="meta">No new products in this option.</p>
          )}

          {option.wardrobe_items_used.length > 0 && (
            <div>
              <div className="meta" style={{ marginBottom: 6 }}>
                From your wardrobe (USD 0)
              </div>
              <div className="chip-row">
                {option.wardrobe_items_used.map((w) => (
                  <span key={w.wardrobe_id} className="badge badge-muted">
                    {w.colour} {w.type}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** Status banner + feedback-loop / retry summary shown atop a plan. */
export function PlanStatusBanner({
  status,
  buyNothingAvailable,
  notes,
  retryLog,
  budgetSource,
}: {
  status: BudgetStatus;
  buyNothingAvailable: boolean;
  notes?: string | null;
  retryLog: RetrievalRetryLog[];
  budgetSource: BudgetSource;
}) {
  const meta = budgetStatusMeta(status, { buyNothingAvailable });
  const categories = retryLog.map((r) => r.category).filter((v, i, a) => a.indexOf(v) === i);
  return (
    <div className="panel stack">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Budget plan</h2>
        <span className={meta.badgeClass}>{meta.label}</span>
      </div>
      <p style={{ margin: 0 }}>{meta.message}</p>
      <p className="meta" style={{ margin: 0 }}>
        Budget source:
        {budgetSource === 'user_stated' ? ' your stated budget' : ' the retrieval price ceiling'}
      </p>
      {categories.length > 0 && (
        <p className="meta" style={{ margin: 0 }}>
          Asked the catalogue for cheaper options on {categories.join(', ')}
          {retryLog.some((r) => r.new_products_found > 0)
            ? ' — cheaper items were found and included.'
            : ' — no cheaper items were returned.'}
        </p>
      )}
      {notes && (
        <p className="meta" style={{ margin: 0 }}>
          {notes}
        </p>
      )}
    </div>
  );
}

/** Small helper: consistent error text for plan calls (quota, clarification). */
export function planErrorText(err: unknown): string {
  const status = (err as { response?: { status?: number } }).response?.status;
  if (status === 429) return extractErrorMessage(err, 'Monthly limit reached.');
  return extractErrorMessage(err, 'Could not build the budget plan.');
}
