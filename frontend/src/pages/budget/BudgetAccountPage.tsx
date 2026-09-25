import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LoadingSkeleton } from '../../components/LoadingSkeleton';
import { ErrorAlert } from '../../components/ErrorAlert';
import {
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

      <div className="split-2">
        <div className="panel stack">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0 }}>This month</h2>
            <span className={`badge ${usage?.tier === 'premium' ? 'badge-ok' : 'badge-muted'}`}>
              {usage?.tier ?? 'free'}
            </span>
          </div>
          {usage && (
            <>
              <p style={{ margin: 0 }}>
                {usage.recommendations_used} of{' '}
                {usage.monthly_limit === -1 ? 'unlimited' : usage.monthly_limit} plans used ·{' '}
                {usage.monthly_limit === -1
                  ? 'no limit'
                  : `${Math.max(usage.monthly_limit - usage.recommendations_used, 0)} left`}
              </p>
              {usage.tier === 'free' && (
                <>
                  <p className="meta" style={{ margin: 0 }}>
                    Premium: {usage.premium_benefits.join('; ')} —{' '}
                    {formatUsd(usage.premium_price_usd)}/month.
                  </p>
                  <div>
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void upgrade()}
                      disabled={upgrading}
                    >
                      {upgrading ? 'Upgrading…' : 'Upgrade to premium'}
                    </button>
                  </div>
                </>
              )}
              {upgradeNote && <p className="meta" style={{ margin: 0 }}>{upgradeNote}</p>}
            </>
          )}
        </div>

        <div className="panel stack">
          <h2 style={{ margin: 0 }}>Saved plans</h2>
          {plans.length === 0 ? (
            <p className="meta">
              No plans built in this browser session yet. Run a{' '}
              <Link to="/request">fashion request</Link>, retrieve products, then build a budget
              plan.
            </p>
          ) : (
            <table style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }} className="meta">When</th>
                  <th style={{ textAlign: 'left' }} className="meta">Request</th>
                  <th style={{ textAlign: 'left' }} className="meta">Ceiling</th>
                  <th style={{ textAlign: 'left' }} className="meta">Status</th>
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
                      <td className="meta">{new Date(p.at).toLocaleTimeString()}</td>
                      <td>
                        <Link to={`/budget/${encodeURIComponent(p.request_id)}`}>
                          {p.query_label || p.request_id}
                        </Link>
                      </td>
                      <td>{formatUsd(p.budget_ceiling)}</td>
                      <td>
                        {m ? (
                          <span className={m.badgeClass}>{m.label}</span>
                        ) : (
                          <span className="badge badge-muted">{p.status}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div className="panel">
        <h2>Product views</h2>
        {clicks.length === 0 ? (
          <p className="meta">
            You haven&rsquo;t opened a product from a budget plan in this account yet.
          </p>
        ) : (
          <table style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left' }} className="meta">When</th>
                <th style={{ textAlign: 'left' }} className="meta">Product</th>
                <th style={{ textAlign: 'left' }} className="meta">Store</th>
                <th style={{ textAlign: 'left' }} className="meta">Price</th>
              </tr>
            </thead>
            <tbody>
              {clicks.map((c, i) => {
                const safeUrl =
                  c.product_url && /^https:\/\//i.test(c.product_url) ? c.product_url : null;
                return (
                  <tr key={`${c.product_id}-${c.clicked_at}-${i}`}>
                    <td className="meta">{new Date(c.clicked_at).toLocaleString()}</td>
                    <td>
                      {safeUrl ? (
                        <a href={safeUrl} target="_blank" rel="noopener noreferrer">
                          {c.product_name ?? c.product_id}
                        </a>
                      ) : (
                        (c.product_name ?? c.product_id)
                      )}
                    </td>
                    <td>{c.store ?? '—'}</td>
                    <td>{formatUsd(c.price_usd) ?? 'not listed'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
