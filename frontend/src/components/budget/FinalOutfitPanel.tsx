import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { ErrorAlert } from '../ErrorAlert';
import { LoadingSkeleton } from '../LoadingSkeleton';
import { buildDecisionContext, recommendOutfit } from '../../services/decisionService';
import { formatScorePercent, formatUsd, strategyLabel } from '../../services/budgetFormat';
import { extractErrorMessage } from '../../services/api';
import type {
  CandidateMetrics,
  DecisionResponse,
  OutfitPiece,
  RejectReasonCode,
  ScoredCandidate,
  SubScoreKey,
  SuggestedAction,
} from '../../types/decision';

interface Props {
  requestId: string;
  userId?: number | string | null;
}

const STATUS_META: Record<string, { label: string; badgeClass: string }> = {
  complete: { label: 'Complete outfit', badgeClass: 'badge badge-ok' },
  partial: { label: 'Partial outfit', badgeClass: 'badge badge-warn' },
  no_suitable_outfit: { label: 'No suitable outfit', badgeClass: 'badge badge-danger' },
  insufficient_input: { label: 'Not ready yet', badgeClass: 'badge badge-muted' },
};

const CONFIDENCE_CLASS: Record<string, string> = {
  high: 'badge badge-ok',
  medium: 'badge badge-warn',
  low: 'badge badge-danger',
};

const REASON_LABEL: Record<RejectReasonCode, string> = {
  STYLE_CLASH: 'Style clash',
  MISSING_REQUIRED_CATEGORY: 'Missing category',
  OVER_BUDGET: 'Over budget',
  CONSTRAINT_VIOLATION: 'Requirement not met',
  LOW_CONFIDENCE: 'Low confidence',
  INCOMPLETE_OUTFIT: 'Incomplete outfit',
};

const ACTION_LABEL: Record<SuggestedAction, string> = {
  retry_with_exclusions: 'Re-plan without these items',
  increase_budget: 'Raise the budget',
  relax_constraints: 'Relax a requirement',
  accept_best_available: 'Accept the best available answer',
  request_clarification: 'Ask what was meant',
};

const SUB_SCORE_FACTORS: { key: SubScoreKey; label: string }[] = [
  { key: 'colour_harmony', label: 'Colour harmony' },
  { key: 'formality_match', label: 'Formality match' },
  { key: 'occasion_fit', label: 'Occasion fit' },
  { key: 'budget_fit', label: 'Budget fit' },
  { key: 'constraint_satisfaction', label: 'Requirements met' },
];

const CHECK_NOTE_LABEL: Record<string, string> = {
  amount_not_in_data: 'Price not in the plan',
  arithmetic_mismatch: 'Budget totals do not add up',
  name_not_in_data: 'Item name not found',
  colour_not_in_data: 'Colour not on a chosen item',
  unverifiable_claim: 'Claim that cannot be checked',
  store_not_in_data: 'Store not in the plan',
  identifier_not_in_data: 'Reference not in the plan',
};

function checkNote(issue: string): string {
  const cut = issue.indexOf(':');
  if (cut < 0) return CHECK_NOTE_LABEL[issue.trim()] ?? 'Wording check note';
  const code = issue.slice(0, cut).trim();
  const value = issue.slice(cut + 1).trim();
  return `${CHECK_NOTE_LABEL[code] ?? 'Wording check note'} — ${value}`;
}

/** The final chosen outfit: what to wear from the wardrobe, what to buy, why. */
export function FinalOutfitPanel({ requestId, userId }: Props) {
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [aiExplanations, setAiExplanations] = useState(false);
  const ranFor = useRef<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const ctx = buildDecisionContext(requestId, userId);
      if (!ctx.ok) {
        setDecision(null);
        setError(
          `This page needs the ${ctx.missing.join(', ')} from the same browser session. ` +
            'Open the request that produced this plan to see the final outfit.'
        );
        return;
      }
      setDecision(await recommendOutfit(ctx.request, aiExplanations));
    } catch (err) {
      setDecision(null);
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [requestId, userId, aiExplanations]);

  // Deciding costs nothing against the monthly limit, so it runs automatically
  // once per plan view; the toggle re-decides with polished wording.
  useEffect(() => {
    if (ranFor.current === `${requestId}:${aiExplanations}`) return;
    ranFor.current = `${requestId}:${aiExplanations}`;
    void run();
  }, [run, requestId, aiExplanations]);

  if (loading && !decision) {
    return <LoadingSkeleton rows={5} />;
  }

  if (!decision) {
    return (
      <div className="stack">
        <ErrorAlert message={error} />
        {error && (
          <div>
            <Link className="btn btn-secondary" to="/request">
              Start from a request
            </Link>
          </div>
        )}
      </div>
    );
  }

  const status = STATUS_META[decision.decision.status] ?? STATUS_META.partial;
  const owned = decision.outfit.filter((p) => p.source === 'wardrobe');
  const toBuy = decision.outfit.filter((p) => p.source === 'purchase');

  const optionNames = new Map<string, string>();
  decision.alternatives.forEach((a) => optionNames.set(a.combination_id, a.name));
  (decision.candidate_rejections ?? []).forEach((r) => optionNames.set(r.combination_id, r.name));
  const rejections = decision.candidate_rejections ?? [];
  // Item swaps are phrased in catalogue ids and option keys a shopper cannot act
  // on, so they stay in the API response and the audit log but off this screen.
  const counterfactuals = (decision.counterfactuals ?? []).filter(
    (c) => c.kind !== 'item_swap'
  );
  const verificationIssues = decision.verification_issues ?? [];

  return (
    <div className="stack">
      <div className="panel stack">
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0 }}>Your recommended outfit</h2>
          <div className="row" style={{ gap: 10, alignItems: 'center' }}>
            <button
              type="button"
              className={`chip ${aiExplanations ? 'active' : ''}`}
              onClick={() => setAiExplanations(!aiExplanations)}
              disabled={loading}
            >
              AI explanations
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => void run()}
              disabled={loading}
            >
              {loading ? 'Checking…' : 'Re-check outfit'}
            </button>
          </div>
        </div>

        <ErrorAlert message={error} />

        <div className="row" style={{ gap: 8, alignItems: 'center' }}>
          <span className={status.badgeClass}>{status.label}</span>
          <span className={CONFIDENCE_CLASS[decision.decision.confidence_level] ?? 'badge badge-muted'}>
            {decision.decision.confidence_level} confidence ·{' '}
            {formatScorePercent(decision.decision.confidence_score)}
          </span>
          {decision.strategy && <span className="meta">{strategyLabel(decision.strategy)}</span>}
          {decision.explanation_verified != null && (
            <span
              className={decision.explanation_verified ? 'badge badge-ok' : 'badge badge-warn'}
            >
              {decision.explanation_verified ? 'Wording checked' : 'Wording simplified'}
            </span>
          )}
          {decision.retry_limit_reached && (
            <span className="badge badge-warn">Best available answer</span>
          )}
        </div>

        <p style={{ margin: 0 }}>{decision.explanation}</p>

        {decision.decision.status !== 'no_suitable_outfit' &&
          decision.decision.status !== 'insufficient_input' && (
            <div className="split-2">
              <PieceGroup
                title="From your wardrobe"
                subtitle={`${decision.purchase_summary.existing_items_used} reused`}
                pieces={owned}
                zeroSpend
              />
              <PieceGroup
                title="To buy"
                subtitle={`${decision.purchase_summary.purchase_count} new item${
                  decision.purchase_summary.purchase_count === 1 ? '' : 's'
                }`}
                pieces={toBuy}
              />
            </div>
          )}

        <div className="chip-row">
          <span className="badge badge-muted">
            additional cost {formatUsd(decision.budget.additional_cost_usd) ?? '—'}
          </span>
          <span className="badge badge-muted">
            remaining {formatUsd(decision.budget.remaining_usd) ?? '—'}
          </span>
          <span className={decision.budget.within_budget ? 'badge badge-ok' : 'badge badge-danger'}>
            {decision.budget.within_budget ? 'within budget' : 'over budget'}
          </span>
        </div>

        {decision.metrics && <ScoreBreakdown metrics={decision.metrics} />}

        {(decision.score_breakdown?.length ?? 0) > 0 && (
          <FactorComparison
            candidates={decision.score_breakdown ?? []}
            nameFor={(id) =>
              optionNames.get(id) ?? (id === decision.selected_combination_id ? 'Chosen outfit' : id)
            }
          />
        )}

        {verificationIssues.length > 0 && (
          <details className="score-box">
            <summary className="meta" style={{ cursor: 'pointer' }}>
              Wording check notes
            </summary>
            <div style={{ marginTop: 8 }}>
              {verificationIssues.map((issue, i) => (
                <div key={`${issue}:${i}`} className="meta">
                  {checkNote(issue)}
                </div>
              ))}
            </div>
          </details>
        )}

        {decision.decision_id && (
          <div className="meta">Decision reference {decision.decision_id}</div>
        )}

        {decision.unresolved_requirements.length > 0 && (
          <p className="meta" style={{ margin: 0 }}>
            Still missing: {decision.unresolved_requirements.join(', ')}.
          </p>
        )}
      </div>

      {rejections.length > 0 && (
        <div className="panel stack">
          <h3 style={{ margin: 0 }}>Why the other options lost</h3>
          {rejections.map((r) => (
            <div key={r.combination_id}>
              <div style={{ fontWeight: 600 }}>{r.name}</div>
              <div className="chip-row">
                {r.reason_codes.map((code) => (
                  <span key={code} className="badge badge-muted">
                    {REASON_LABEL[code] ?? code}
                  </span>
                ))}
              </div>
              {r.detail && <div className="meta">{r.detail}</div>}
            </div>
          ))}
          {decision.suggested_action && (
            <div className="meta">Next step: {ACTION_LABEL[decision.suggested_action]}</div>
          )}
          {decision.retry_limit_reason && (
            <p className="meta" style={{ margin: 0 }}>
              {decision.retry_limit_reason}
            </p>
          )}
        </div>
      )}

      {counterfactuals.length > 0 && (
        <div className="panel stack">
          <h3 style={{ margin: 0 }}>What would change this answer</h3>
          {counterfactuals.map((c, i) => (
            <div key={`${c.kind}:${i}`} className="meta">
              {c.sentence}
            </div>
          ))}
        </div>
      )}

      {decision.alternatives.length > 0 && (
        <div className="panel stack">
          <h3 style={{ margin: 0 }}>Other options considered</h3>
          {decision.alternatives.map((a) => (
            <div key={a.combination_id} className="row" style={{ justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontWeight: 600 }}>{a.name}</div>
                <div className="meta">{a.reason}</div>
              </div>
              <div className="meta" style={{ textAlign: 'right' }}>
                {formatUsd(a.total_cost_usd) ?? '—'}
                <div>Score: {formatScorePercent(a.decision_score)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function PieceGroup({
  title,
  subtitle,
  pieces,
  zeroSpend = false,
}: {
  title: string;
  subtitle: string;
  pieces: OutfitPiece[];
  zeroSpend?: boolean;
}) {
  return (
    <div>
      <div className="row" style={{ gap: 6, alignItems: 'center' }}>
        <div className="meta">{title}</div>
        {zeroSpend && pieces.length > 0 && (
          <span className="badge badge-muted">
            <Sparkles size={12} style={{ verticalAlign: -2 }} /> zero spend
          </span>
        )}
      </div>
      <div style={{ marginTop: 6 }}>
        {pieces.length === 0 ? (
          <p className="meta">None.</p>
        ) : (
          pieces.map((p) => (
            <div key={`${p.source}:${p.item_id}`} style={{ marginBottom: 6 }}>
              <div style={{ textTransform: 'capitalize' }}>
                {p.category}: {p.name}
              </div>
              <div className="meta">
                {p.price_usd != null && p.price_usd > 0
                  ? `${formatUsd(p.price_usd)}${p.store ? ` · ${p.store}` : ''}`
                  : p.role}
              </div>
            </div>
          ))
        )}
      </div>
      <div className="meta">{subtitle}</div>
    </div>
  );
}

const SCORE_FACTORS: { key: keyof CandidateMetrics; label: string }[] = [
  { key: 'occasion_fit', label: 'Occasion fit' },
  { key: 'style_fit', label: 'Style fit' },
  { key: 'colour_fit', label: 'Colour fit' },
  { key: 'wardrobe_reuse', label: 'Wardrobe reuse' },
  { key: 'retrieval_relevance', label: 'Product relevance' },
  { key: 'budget_efficiency', label: 'Budget efficiency' },
];

function ScoreBreakdown({ metrics }: { metrics: CandidateMetrics }) {
  return (
    <details className="score-box">
      <summary className="meta" style={{ cursor: 'pointer' }}>
        Score breakdown
      </summary>
      <div style={{ marginTop: 8 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span style={{ fontWeight: 600 }}>Overall match score</span>
          <span style={{ fontWeight: 600 }}>{formatScorePercent(metrics.decision_score)}</span>
        </div>
        <ScoreBar value={metrics.decision_score} />
        {SCORE_FACTORS.map((f) => {
          const v = metrics[f.key] as number;
          return (
            <div key={f.key} className="row score-row">
              <span className="meta">{f.label}</span>
              <ScoreBar value={v} compact />
              <span className="meta">{formatScorePercent(v)}</span>
            </div>
          );
        })}
      </div>
    </details>
  );
}

function ScoreBar({ value, compact = false }: { value: number; compact?: boolean }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <span
      className={`score-bar ${compact ? 'score-bar-compact' : ''}`}
      aria-hidden="true"
    >
      <span className="score-bar-fill" style={{ width: `${pct}%` }} />
    </span>
  );
}

/** Weighted factor view: the chosen outfit and each runner-up on the same five axes. */
function FactorComparison({
  candidates,
  nameFor,
}: {
  candidates: ScoredCandidate[];
  nameFor: (combinationId: string) => string;
}) {
  return (
    <details className="score-box" open={candidates.length > 1}>
      <summary className="meta" style={{ cursor: 'pointer' }}>
        How the options were compared
      </summary>
      <div style={{ marginTop: 8 }}>
        {candidates.map((c) => (
          <div key={c.combination_id} style={{ marginBottom: 10 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 600 }}>
                {c.rank}. {nameFor(c.combination_id)}
              </span>
              <span className="meta">
                {formatScorePercent(c.overall_score)}
                {c.selected ? ' · chosen' : ''}
              </span>
            </div>
            {SUB_SCORE_FACTORS.map((f) => (
              <div key={f.key} className="row score-row">
                <span className="meta">{f.label}</span>
                <ScoreBar value={c.sub_scores[f.key]} compact />
                <span className="meta score-values">
                  <span>Score: {formatScorePercent(c.sub_scores[f.key])}</span>
                  <span>Weight: {formatScorePercent(c.weights[f.key])}</span>
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </details>
  );
}
