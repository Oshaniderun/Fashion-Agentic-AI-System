import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LoadingSkeleton } from '../../components/LoadingSkeleton';
import { ErrorAlert } from '../../components/ErrorAlert';
import {
  clearAffiliateHistory,
  getAffiliateHistory,
  getUsage,
  upgradeToPremium,
  type AffiliateClickRow,
  type UpgradeResult,
} from '../../services/budgetService';
import { readPlanRefs, type SavedPlanRef } from '../../services/budgetHistory';
import { formatUsd, budgetStatusMeta } from '../../services/budgetFormat';
import { extractErrorMessage } from '../../services/api';
import type { BudgetStatus, UsageStats } from '../../types/budget';

export function BudgetAccountPage() {
  const { user } = useAuth();
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [clicks, setClicks] = useState<AffiliateClickRow[]>([]);
  const [plans, setPlans] = useState<SavedPlanRef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [upgrading, setUpgrading] = useState(false);
  const [upgradeNote, setUpgradeNote] = useState('');
  const [clearing, setClearing] = useState(false);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      const [u, h] = await Promise.all([getUsage(user.id), getAffiliateHistory(user.id)]);
      setUsage(u);
      setClicks(h.clicks);
      setPlans(readPlanRefs());
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void load();
  }, [load]);

  const upgrade = async () => {
    if (!user) return;
    setUpgrading(true);
    setUpgradeNote('');
    try {
      const res: UpgradeResult = await upgradeToPremium(String(user.id));
      setUpgradeNote(res.message);
      await load();
    } catch (err) {
      setUpgradeNote(extractErrorMessage(err));
    } finally {
      setUpgrading(false);
    }
  };

  const clearViews = async () => {
    if (!user) return;
    if (!window.confirm('Clear your product views list? This cannot be undone.')) return;
    setClearing(true);
    setError('');
    try {
      await clearAffiliateHistory(user.id);
      setClicks([]);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setClearing(false);
    }
  };

  if (loading) {
    return (
      <div className="page">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Budget</h1>
        <p>Plans from this session, monthly limit, and product views you made.</p>
      </div>

      <ErrorAlert message={error} />

      {usage && (
        <div className="grid-stats grid-stats-auto">
          <div className="stat">
            <div className="label">Plans used</div>
            <div className="value">{usage.recommendations_used}</div>
            <div className="meta">
              {usage.monthly_limit === -1
                ? 'unlimited plan'
                : `of ${usage.monthly_limit} this month`}
            </div>
          </div>
          <div className="stat">
            <div className="label">Left this month</div>
            <div className="value">
              {usage.recommendations_remaining === -1 ? '∞' : usage.recommendations_remaining}
            </div>
            <div className="meta">{monthLabel(usage.month)}</div>
          </div>
          <div className="stat">
            <div className="label">Product views</div>
            <div className="value">{clicks.length}</div>
            <div className="meta">{usage.tier === 'premium' ? 'premium' : 'free'} plan</div>
          </div>
        </div>
      )}

      {usage?.tier === 'free' && (
        <div className="panel" style={{ marginTop: '1rem' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <p style={{ margin: 0 }}>
                Premium — {usage.premium_benefits.join('; ')} —{' '}
                {formatUsd(usage.premium_price_usd)}/month.
              </p>
              {upgradeNote && <p className="meta" style={{ margin: 0 }}>{upgradeNote}</p>}
            </div>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => void upgrade()}
              disabled={upgrading}
            >
              {upgrading ? 'Upgrading…' : 'Upgrade to premium'}
            </button>
          </div>
        </div>
      )}

      <div className="split-2" style={{ marginTop: '1rem', alignItems: 'start' }}>
        <div className="panel">
          <h2>Saved plans</h2>
          {plans.length === 0 ? (
            <p className="meta">
              No plans built in this browser session yet. Run a{' '}
              <Link to="/request">fashion request</Link>, retrieve products, then build a budget
              plan.
            </p>
          ) : (
            <table className="table-fixed">
              <thead>
                <tr>
                  <th className="meta">Request</th>
                  <th className="meta" style={{ width: 118 }}>Ceiling</th>
                  <th className="meta" style={{ width: 152 }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {plans.map((p) => {
                  const known = (
                    ['within_budget', 'exceeds_budget', 'partially_feasible', 'no_purchase_needed'] as string[]
                  ).includes(p.status);
                  const m = known
                    ? budgetStatusMeta(p.status as BudgetStatus, { buyNothingAvailable: false })
                    : null;
                  return (
                    <tr key={p.request_id}>
                      <td>
                        <Link to={`/budget/${encodeURIComponent(p.request_id)}`} className="clip">
                          {p.query_label || p.request_id}
                        </Link>
                        <div className="meta">{new Date(p.at).toLocaleTimeString()}</div>
                      </td>
                      <td className="num">{formatUsd(p.budget_ceiling)}</td>
                      <td>
                        {m ? (
                          <span className={m.badgeClass} style={{ whiteSpace: 'nowrap' }}>
                            {m.label}
                          </span>
                        ) : (
                          <span className="badge badge-muted" style={{ whiteSpace: 'nowrap' }}>
                            {p.status}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        <div className="panel">
          <div
            className="row"
            style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}
          >
            <h2 style={{ margin: 0 }}>Product views</h2>
            {clicks.length > 0 && (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => void clearViews()}
                disabled={clearing}
              >
                {clearing ? 'Clearing…' : 'Clear'}
              </button>
            )}
          </div>
          {clicks.length === 0 ? (
            <p className="meta">You haven&rsquo;t opened a product listing in this account yet.</p>
          ) : (
            <table className="table-fixed">
              <thead>
                <tr>
                  <th className="meta">Product</th>
                  <th className="meta" style={{ width: 104 }}>Price</th>
                </tr>
              </thead>
              <tbody>
                {clicks.map((c, i) => {
                  const label = c.product_name ?? c.product_id;
                  return (
                    <tr key={`${c.product_id}-${c.clicked_at}-${i}`}>
                      <td>
                        <span className="clip">{label}</span>
                        <div className="meta">
                          {c.store ?? '—'} · {new Date(c.clicked_at).toLocaleString()}
                        </div>
                      </td>
                      <td className="num">{formatUsd(c.price_usd) ?? 'not listed'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function monthLabel(month: string): string {
  const date = new Date(`${month}-01T00:00:00`);
  if (Number.isNaN(date.getTime())) return month;
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}
