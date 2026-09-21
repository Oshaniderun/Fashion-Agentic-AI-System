import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listWardrobe } from '../services/wardrobeService';
import { getLatestAnalysis } from '../services/analysisService';
import { getAgentStatus } from '../services/agentService';
import { extractErrorMessage, imageUrl } from '../services/api';
import type { AgentStatus, FashionAnalysisResponse, WardrobeItem } from '../types';
import { ErrorAlert } from '../components/ErrorAlert';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { MissingItemsBadge } from '../components/MissingItemsBadge';

function countBy(items: WardrobeItem[], pred: (i: WardrobeItem) => boolean) {
  return items.filter(pred).length;
}

export function Dashboard() {
  const [items, setItems] = useState<WardrobeItem[]>([]);
  const [latest, setLatest] = useState<FashionAnalysisResponse | null>(null);
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listWardrobe(), getLatestAnalysis(), getAgentStatus()])
      .then(([wardrobe, analysis, agent]) => {
        setItems(wardrobe);
        setLatest(analysis);
        setStatus(agent);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="page">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const recent = [...items].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at)).slice(0, 4);

  return (
    <div className="page">
      <div className="page-header">
        <h1>FASHORA</h1>
        <p>Style & Wardrobe Intelligence — understand what you own, what you want, and what may be missing.</p>
      </div>

      <ErrorAlert message={error} />

      <div className="grid-stats">
        <div className="stat">
          <div className="label">Wardrobe</div>
          <div className="value">{items.length}</div>
        </div>
        <div className="stat">
          <div className="label">Tops</div>
          <div className="value">{countBy(items, (i) => i.category === 'top')}</div>
        </div>
        <div className="stat">
          <div className="label">Bottoms</div>
          <div className="value">{countBy(items, (i) => i.category === 'bottom')}</div>
        </div>
        <div className="stat">
          <div className="label">Footwear</div>
          <div className="value">{countBy(items, (i) => i.category === 'shoes')}</div>
        </div>
        <div className="stat">
          <div className="label">Other</div>
          <div className="value">
            {countBy(items, (i) => !['top', 'bottom', 'shoes'].includes(i.category))}
          </div>
        </div>
      </div>

      <div className="split-2" style={{ marginTop: '1rem' }}>
        <div className="panel">
          <h2>Recent wardrobe additions</h2>
          {recent.length === 0 ? (
            <p className="meta">No items yet. Add clothing to get started.</p>
          ) : (
            <div className="stack">
              {recent.map((item) => (
                <Link key={item.id} to={`/wardrobe/${item.id}`} className="row">
                  <img
                    src={imageUrl(item.image_url)}
                    alt=""
                    style={{ width: 48, height: 48, borderRadius: 8, objectFit: 'cover' }}
                  />
                  <div>
                    <strong style={{ textTransform: 'capitalize' }}>
                      {item.colour} {item.type}
                    </strong>
                    <div className="meta">{item.wardrobe_code}</div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div className="stack">
          <div className="panel">
            <h2>Agent status</h2>
            {status ? (
              <>
                <span className={`badge ${status.status === 'healthy' ? 'badge-ok' : 'badge-warn'}`}>
                  {status.status}
                </span>
                <p className="meta" style={{ marginTop: 8 }}>
                  {status.agent} · v{status.version}
                </p>
              </>
            ) : (
              <p className="meta">Unavailable</p>
            )}
          </div>

          <div className="panel">
            <h2>Last analysis</h2>
            {latest ? (
              <>
                <p style={{ margin: '0 0 0.5rem' }}>&ldquo;{latest.input_text}&rdquo;</p>
                <p className="meta">
                  {latest.compatible_items.length} wardrobe items usable ·{' '}
                  {latest.outfit_requirements.missing_categories.length} category missing
                </p>
                <div style={{ marginTop: 8 }}>
                  <MissingItemsBadge outfit={latest.outfit_requirements} />
                </div>
                <Link className="btn btn-secondary" style={{ marginTop: 12 }} to={`/analysis/${latest.request_id}`}>
                  View result
                </Link>
              </>
            ) : (
              <p className="meta">No analysis yet.</p>
            )}
          </div>
        </div>
      </div>

      <div style={{ marginTop: '1.25rem' }}>
        <Link className="btn btn-primary" to="/request">
          Analyze New Outfit
        </Link>
      </div>
    </div>
  );
}
