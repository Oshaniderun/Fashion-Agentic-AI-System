import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { RequirementSummary } from '../components/RequirementSummary';
import { MissingItemsBadge } from '../components/MissingItemsBadge';
import { CompatibilityMeter } from '../components/CompatibilityMeter';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { ErrorAlert } from '../components/ErrorAlert';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { getAnalysis } from '../services/analysisService';
import { extractErrorMessage, imageUrl } from '../services/api';
import type { FashionAnalysisResponse } from '../types';

export function AnalysisResult() {
  const { requestId } = useParams();
  const [data, setData] = useState<FashionAnalysisResponse | null>(null);
  const [tab, setTab] = useState<'overview' | 'json'>('overview');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

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

  const copyJson = async () => {
    if (!data) return;
    await navigator.clipboard.writeText(JSON.stringify(data.raw_agent1_contract, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

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
          Request <code>{data.request_id}</code> — AI extraction vs owned wardrobe. Agent 1 does not buy or rank
          products.
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
        <button type="button" className={`chip ${tab === 'json' ? 'active' : ''}`} onClick={() => setTab('json')}>
          Agent 1 JSON
        </button>
        <ConfidenceBadge value={data.confidence.overall} label="Overall" />
      </div>

      {tab === 'json' ? (
        <div className="panel stack">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <h2 style={{ margin: 0 }}>Structured contract for Agent 2</h2>
            <button type="button" className="btn btn-secondary" onClick={copyJson}>
              {copied ? 'Copied' : 'Copy for Agent 2'}
            </button>
          </div>
          <pre className="code-block">{JSON.stringify(data.raw_agent1_contract, null, 2)}</pre>
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
                <div className="meta">Available from wardrobe</div>
                <div className="chip-row" style={{ marginTop: 6 }}>
                  {data.outfit_requirements.available_categories.map((c) => (
                    <span key={c} className="badge badge-ok">
                      ✓ {c}
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
                      <span className="badge badge-muted">{item.wardrobe_id}</span>
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

          <div className="panel">
            <h2>Agent 2 handoff preview</h2>
            <pre className="code-block">{JSON.stringify(data.search_requirements, null, 2)}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
