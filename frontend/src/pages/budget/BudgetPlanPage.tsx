import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { LoadingSkeleton } from '../../components/LoadingSkeleton';
import { ErrorAlert } from '../../components/ErrorAlert';
import { OutfitOptionCard, PlanStatusBanner } from '../../components/budget/OutfitOptionCard';
import { readCachedPlan } from '../../services/budgetHistory';
import { compareOptions, type ComparisonResult } from '../../services/budgetService';
import { formatUsd, strategyLabel } from '../../services/budgetFormat';
import { extractErrorMessage } from '../../services/api';
import type { BudgetOptimizationResponse } from '../../types/budget';

type Tab = 'options' | 'comparison';

export function BudgetPlanPage() {
  const { requestId } = useParams();
  const { user } = useAuth();
  const [plan, setPlan] = useState<BudgetOptimizationResponse | null>(null);
  const [tab, setTab] = useState<Tab>('options');
  const [comparison, setComparison] = useState<ComparisonResult | null>(null);
  const [cmpLoading, setCmpLoading] = useState(false);
  const [cmpError, setCmpError] = useState('');

  useEffect(() => {
    if (!requestId) return;
    setPlan(readCachedPlan<BudgetOptimizationResponse>(requestId));
  }, [requestId]);

  useEffect(() => {
    if (tab !== 'comparison' || !plan || comparison || cmpLoading) return;
    setCmpLoading(true);
    setCmpError('');
    compareOptions(plan.options, plan.budget_ceiling)
      .then(setComparison)
      .catch((err) => setCmpError(extractErrorMessage(err)))
      .finally(() => setCmpLoading(false));
  }, [tab, plan, comparison, cmpLoading]);

  if (!requestId) return null;

  if (!plan) {
    return (
      <div className="page">
        <div className="panel stack">
          <h1 style={{ margin: 0 }}>Budget plan</h1>
          <p className="meta">
            No saved plan for request <code>{requestId}</code> in this browser session. Run a
            retrieval and build a plan from an <Link to="/request">analysis result</Link> first.
          </p>
          <div>
            <Link className="btn btn-primary" to="/request">
              New request
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const recommended = plan.options.find(
    (o) => o.combination_id === plan.recommended_option_id
  );

  return (
    <div className="page">
      <div className="page-header">
        <h1>Budget plan</h1>
        <p>
          Request <code>{plan.request_id}</code> · ceiling {formatUsd(plan.budget_ceiling)} ·{' '}
          {plan.options.length} option{plan.options.length === 1 ? '' : 's'}
        </p>
      </div>

      <div className="row" style={{ marginBottom: '1rem' }}>
        <button
          type="button"
          className={`chip ${tab === 'options' ? 'active' : ''}`}
          onClick={() => setTab('options')}
        >
          Options
        </button>
        <button
          type="button"
          className={`chip ${tab === 'comparison' ? 'active' : ''}`}
          onClick={() => setTab('comparison')}
        >
          Comparison
        </button>
      </div>

      {tab === 'options' && (
        <div className="stack">
          <PlanStatusBanner
            status={plan.status}
            buyNothingAvailable={plan.buy_nothing_available}
            notes={plan.notes}
            retryLog={plan.retry_log}
            budgetSource={plan.budget_source}
          />
          {plan.options.length === 0 ? (
            <div className="panel">
              <p className="meta" style={{ margin: 0 }}>
                No outfit options were assembled for this plan.
              </p>
            </div>
          ) : (
            plan.options.map((o) => (
              <OutfitOptionCard
                key={o.combination_id}
                requestId={plan.request_id}
                userId={user?.id ?? null}
                option={o}
                recommended={recommended?.combination_id === o.combination_id}
              />
            ))
          )}
          <p className="meta">
            Back to the <Link to={`/analysis/${plan.request_id}`}>analysis result</Link>.
          </p>
        </div>
      )}

      {tab === 'comparison' && (
        <div className="panel stack">
          <h2 style={{ margin: 0 }}>Side-by-side comparison</h2>
          {cmpError && <ErrorAlert message={cmpError} />}
          {cmpLoading && <LoadingSkeleton rows={4} />}
          {comparison && (
            <>
              <table style={{ width: '100%' }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: 'left' }} className="meta">#</th>
                    <th style={{ textAlign: 'left' }} className="meta">Option</th>
                    <th style={{ textAlign: 'left' }} className="meta">Total</th>
                    <th style={{ textAlign: 'left' }} className="meta">Savings</th>
                    <th style={{ textAlign: 'left' }} className="meta">Remaining</th>
                    <th style={{ textAlign: 'left' }} className="meta">Relevance</th>
                    <th style={{ textAlign: 'left' }} className="meta">Value</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.ranked_options.map((r) => (
                    <tr key={r.option_id}>
                      <td>{r.rank}</td>
                      <td>
                        <div style={{ fontWeight: 600 }}>{r.name}</div>
                        <div className="meta">{strategyLabel(r.strategy)}</div>
                      </td>
                      <td>{formatUsd(r.total_cost_usd)}</td>
                      <td>{formatUsd(r.savings_usd)}</td>
                      <td>{formatUsd(r.budget_remaining_usd)}</td>
                      <td>{Math.round(r.relevance_score)}%</td>
                      <td>{Math.round(r.overall_value_score)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="chip-row">
                <span className="badge badge-muted">
                  cheapest {formatUsd(numOr(null, comparison.summary_stats.cheapest_usd)) ?? '—'}
                </span>
                <span className="badge badge-muted">
                  average {formatUsd(numOr(null, comparison.summary_stats.avg_cost_usd)) ?? '—'}
                </span>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function numOr(fallback: number | null, value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}
