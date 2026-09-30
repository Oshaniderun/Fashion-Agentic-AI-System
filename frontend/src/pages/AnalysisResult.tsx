import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { RequirementSummary } from '../components/RequirementSummary';
import { MissingItemsBadge } from '../components/MissingItemsBadge';
import { CompatibilityMeter } from '../components/CompatibilityMeter';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { ErrorAlert } from '../components/ErrorAlert';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { getAnalysis } from '../services/analysisService';
import { searchFromAgent1Handoff } from '../services/agent2Service';
import { statusMeta, describeHttpError } from '../services/agent2Format';
import { planPurchases } from '../services/budgetService';
import { cachePlan, cacheRetrievalContext, readCachedPlan, savePlanRef } from '../services/budgetHistory';
import { planErrorText } from '../components/budget/OutfitOptionCard';
import { useAuth } from '../context/AuthContext';
import { ProductCard } from '../components/ProductCard';
import { extractErrorMessage, imageUrl } from '../services/api';
import type { FashionAnalysisResponse } from '../types';
import type { HandoffRetrievalResponse } from '../types/agent2';
import type { BudgetOptimizationResponse } from '../types/budget';
import type { RetrievalRequest, RetrievalResponse } from '../types/agent2';

export function AnalysisResult() {
  const { requestId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [data, setData] = useState<FashionAnalysisResponse | null>(null);
  const [tab, setTab] = useState<'overview' | 'handoff'>('overview');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [handoff, setHandoff] = useState<HandoffRetrievalResponse | null>(null);
  const [handoffLoading, setHandoffLoading] = useState(false);
  const [handoffError, setHandoffError] = useState('');
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');
  const [aiExplanations, setAiExplanations] = useState(false);
  const [hasSavedPlan, setHasSavedPlan] = useState(false);

  useEffect(() => {
    if (!requestId) return;
    const cached = sessionStorage.getItem(`analysis:${requestId}`);
    if (cached) {
      try {
        setData(JSON.parse(cached) as FashionAnalysisResponse);
        setLoading(false);
        return;
      } catch {
        /* fall through */
      }
    }
    getAnalysis(requestId)
      .then((res) => {
        setData(res);
        sessionStorage.setItem(`analysis:${requestId}`, JSON.stringify(res));
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, [requestId]);

  const runHandoff = async () => {
    if (!data?.agent2_handoff) return;
    setHandoffLoading(true);
    setHandoffError('');
    try {
      const res = await searchFromAgent1Handoff(data.agent2_handoff);
      setHandoff(res);
    } catch (err) {
      setHandoff(null);
      const status = (err as { response?: { status?: number } }).response?.status;
      setHandoffError(status ? describeHttpError(status) : extractErrorMessage(err));
    } finally {
      setHandoffLoading(false);
    }
  };

  // A plan is user-initiated (each one counts against the monthly limit), so
  // it never auto-runs; if one is already cached for this request, link to it.
  useEffect(() => {
    if (!requestId) return;
    setHasSavedPlan(readCachedPlan<BudgetOptimizationResponse>(requestId) !== null);
  }, [requestId]);

  const buildPlan = async () => {
    if (!data?.agent2_handoff) return;
    setPlanLoading(true);
    setPlanError('');
    try {
      const retrieval_by_category: Record<string, RetrievalResponse> = {};
      const retrieval_requests_by_category: Record<string, RetrievalRequest> = {};
      (handoff?.retrievals ?? []).forEach((r) => {
        if (r.response) retrieval_by_category[r.category] = r.response;
        if (r.request) retrieval_requests_by_category[r.category] = r.request;
      });
      const plan = await planPurchases(
        {
          agent1_output: data.raw_agent1_contract,
          retrieval_by_category,
          retrieval_requests_by_category:
            Object.keys(retrieval_requests_by_category).length > 0
              ? retrieval_requests_by_category
              : null,
          user_id: user?.id ?? null,
        },
        aiExplanations
      );
      cachePlan(data.request_id, plan);
      cacheRetrievalContext(data.request_id, retrieval_by_category);
      savePlanRef({
        request_id: data.request_id,
        at: new Date().toISOString(),
        query_label: data.input_text.slice(0, 60),
        budget_ceiling: plan.budget_ceiling,
        status: plan.status,
      });
      navigate(`/budget/${encodeURIComponent(data.request_id)}`);
    } catch (err) {
      setPlanError(planErrorText(err));
    } finally {
      setPlanLoading(false);
    }
  };

  // Auto-run the Agent 2 retrieval once per analysis so results render below the handoff JSON
  // without requiring a click; the button stays as a manual re-run/retry.
  // Skipped when the request needs clarification or nothing was flagged missing.
  const needsClarification = !!data?.outfit_requirements.clarification_needed;
  const autoRanFor = useRef<string | null>(null);
  useEffect(() => {
    if (!data?.agent2_handoff || autoRanFor.current === requestId) return;
    if (data.outfit_requirements.clarification_needed) return;
    if ((data.agent2_handoff.search_requirements?.categories ?? []).length === 0) return;
    autoRanFor.current = requestId ?? null;
    void runHandoff();
  }, [data, requestId]);

  if (loading) {
    return (
      <div className="page">
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page">
        <ErrorAlert message={error || 'Analysis not found'} />
        <Link to="/request" className="btn btn-primary">
          New request
        </Link>
      </div>
    );
  }

  const compatScore = data.compatibility?.score ?? 0;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Analysis Result</h1>
        <p>
          Request <code>{data.request_id}</code> — AI extraction vs owned wardrobe.
        </p>
      </div>

      <div className="row" style={{ marginBottom: '1rem' }}>
        <button
          type="button"
          className={`chip ${tab === 'overview' ? 'active' : ''}`}
          onClick={() => setTab('overview')}
        >
          Overview
        </button>
        <button
          type="button"
          className={`chip ${tab === 'handoff' ? 'active' : ''}`}
          onClick={() => setTab('handoff')}
        >
          Handoff by Agent 1
        </button>
      </div>

      {tab === 'handoff' ? (
        <div className="panel stack">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0 }}>Handoff by Agent 1</h2>
            <p className="meta" style={{ margin: 0 }}>
              Structured package Agent 2 should consume (requirements + wardrobe gaps + search brief).
            </p>
          </div>
          <pre className="code-block">
            {JSON.stringify(data.agent2_handoff ?? data.search_requirements, null, 2)}
          </pre>
        </div>
      ) : (
        <div className="stack">
          <div className="panel">
            <h2>Request</h2>
            <p style={{ margin: 0 }}>&ldquo;{data.input_text}&rdquo;</p>
          </div>

          <div className="split-2">
            <div className="panel">
              <h2>Detected requirements</h2>
              <RequirementSummary requirements={data.user_requirements} />
            </div>
            {needsClarification ? (
              <div className="panel stack">
                <h2>Need a little more detail</h2>
                <p style={{ margin: 0 }}>{data.outfit_requirements.clarification_message}</p>
                <div>
                  <Link className="btn btn-primary" to="/request">
                    Edit request
                  </Link>
                </div>
              </div>
            ) : (
              <div className="panel stack">
                <h2>Outfit categories</h2>
              <div>
                <div className="meta">Required</div>
                <div className="chip-row" style={{ marginTop: 6 }}>
                  {data.outfit_requirements.required_categories.map((c) => (
                    <span key={c} className="badge badge-muted">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="meta">Categories present in wardrobe (not necessarily a match)</div>
                <div className="chip-row" style={{ marginTop: 6 }}>
                  {data.outfit_requirements.available_categories.map((c) => (
                    <span key={c} className="badge badge-muted">
                      {c}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <div className="meta">Possible missing categories</div>
                <div style={{ marginTop: 6 }}>
                  <MissingItemsBadge outfit={data.outfit_requirements} />
                </div>
              </div>
              </div>
            )}
          </div>

          <div className="panel">
            <h2>Compatible wardrobe items</h2>
            {data.compatible_items.length === 0 ? (
              <p className="meta">No strongly matching owned items for this request.</p>
            ) : (
              <div className="wardrobe-grid">
                {data.compatible_items.map((item) => (
                  <div key={item.wardrobe_id} className="wardrobe-card" style={{ cursor: 'default' }}>
                    {item.image_url && (
                      <img src={imageUrl(item.image_url)} alt={`${item.colour} ${item.type}`} />
                    )}
                    <div className="body">
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <span className="badge badge-muted">{item.wardrobe_id}</span>
                        <ConfidenceBadge value={item.confidence} />
                      </div>
                      <h3 style={{ marginTop: 8, textTransform: 'capitalize' }}>
                        {item.colour} {item.type}
                      </h3>
                      <p className="meta">
                        {item.category} · {item.style.replace(/_/g, ' ')}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {data.compatibility && (
            <div className="panel stack">
              <h2>Compatibility (heuristic, not absolute truth)</h2>
              <CompatibilityMeter label="Overall score" score={compatScore} />
              <CompatibilityMeter
                label="Colour"
                score={
                  data.compatibility.colour_compatibility === 'excellent'
                    ? 0.95
                    : data.compatibility.colour_compatibility === 'good'
                      ? 0.8
                      : data.compatibility.colour_compatibility === 'moderate'
                        ? 0.55
                        : 0.3
                }
                qualitative={data.compatibility.colour_compatibility}
              />
              <CompatibilityMeter
                label="Occasion suitability"
                score={
                  data.compatibility.occasion_suitability === 'high'
                    ? 0.9
                    : data.compatibility.occasion_suitability === 'moderate'
                      ? 0.6
                      : 0.35
                }
                qualitative={data.compatibility.occasion_suitability}
              />
              <p className="meta">{data.compatibility.explanation}</p>
              <p>
                Suggested combination style:{' '}
                <strong style={{ textTransform: 'capitalize' }}>
                  {data.compatibility.style.replace(/_/g, ' ')}
                </strong>
              </p>
            </div>
          )}

          {!needsClarification && (
          <>
          <div className="panel stack">
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h2 style={{ margin: 0 }}>Find products</h2>
              <button
                type="button"
                className="btn btn-primary"
                onClick={runHandoff}
                disabled={handoffLoading || !data.agent2_handoff}
              >
                {handoffLoading ? 'Retrieving…' : handoff ? 'Re-run retrieval' : 'Retrieve missing items'}
              </button>
            </div>
            {!data.agent2_handoff && (
              <p className="meta">
                No Agent 2 handoff payload is available for this analysis, so retrieval cannot be run.
              </p>
            )}

            <ErrorAlert message={handoffError} />

            {handoff && (
              <div className="stack">
                <p className="meta">
                  Price ceiling used: <strong>{handoff.price_ceiling_used.toLocaleString()} {handoff.price_currency}</strong>
                  {' '}· request <code>{handoff.request_id}</code>
                </p>
                {handoff.warnings.map((w) => (
                  <div key={w} className="alert alert-info">
                    {w}
                  </div>
                ))}

                {handoff.retrievals.length === 0 && (
                  <p className="meta">Agent 2 reported nothing to retrieve for this handoff.</p>
                )}

                {handoff.retrievals.map((r) => {
                  if (r.error) {
                    return (
                      <div key={r.category} className="alert alert-error">
                        {r.category}: {r.error}
                      </div>
                    );
                  }
                  const m = r.response ? statusMeta(r.response.status, r.response.relaxed_constraints) : null;
                  return (
                    <div key={r.category} className="panel">
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <h3 style={{ margin: 0, textTransform: 'capitalize' }}>{r.category}</h3>
                        {m && <span className={m.badgeClass}>{m.label}</span>}
                      </div>
                      {m && <p className="meta">{m.message}</p>}
                      {r.response && r.response.results.length > 0 ? (
                        <div className="wardrobe-grid" style={{ marginTop: 10 }}>
                          {r.response.results.map((p) => (
                            <ProductCard
                              key={p.product_id}
                              product={p}
                              currency={handoff.price_currency}
                            />
                          ))}
                        </div>
                      ) : (
                        <p className="meta">No products returned for this category.</p>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="panel stack">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>Budget plan</h2>
              <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                <button
                  type="button"
                  className={`chip ${aiExplanations ? 'active' : ''}`}
                  onClick={() => setAiExplanations(!aiExplanations)}
                >
                  AI explanations
                </button>
                {hasSavedPlan && (
                  <Link
                    className="btn btn-secondary"
                    to={`/budget/${encodeURIComponent(data.request_id)}`}
                  >
                    Open saved plan
                  </Link>
                )}
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => void buildPlan()}
                  disabled={planLoading || !data.agent2_handoff}
                >
                  {planLoading ? 'Planning…' : 'Build budget plan'}
                </button>
              </div>
            </div>
            <ErrorAlert message={planError} />
          </div>
          </>
          )}
        </div>
      )}
    </div>
  );
}
