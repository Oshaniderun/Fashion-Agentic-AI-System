import { useEffect, useState } from 'react';
import { ErrorAlert } from '../../components/ErrorAlert';
import { LoadingSkeleton } from '../../components/LoadingSkeleton';
import { getAgent2Status } from '../../services/agent2Service';
import { describeHttpError } from '../../services/agent2Format';
import { extractErrorMessage } from '../../services/api';
import type { Agent2Status } from '../../types/agent2';

function fmt(n: number | null | undefined): string {
  return n === null || n === undefined ? 'unavailable' : n.toLocaleString();
}

function yesNo(v: boolean | null | undefined): string {
  if (v === null || v === undefined) return 'unknown';
  return v ? 'yes' : 'no';
}

export function Agent2StatusPage() {
  const [status, setStatus] = useState<Agent2Status | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    getAgent2Status()
      .then((s) => setStatus(s))
      .catch((err) => {
        setStatus(null);
        setError(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (err as any)?.response ? describeHttpError((err as any).response.status) : extractErrorMessage(err)
        );
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const healthy = !!status && status.database_connected && status.bm25_index_loaded && !!status.chroma_connected;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Agent 2 · Service status</h1>
        <p>Live inspection of the catalogue, indexes and embedding model. Nulls mean the probe failed — never a fake green.</p>
      </div>

      <div className="row" style={{ marginBottom: '1rem' }}>
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>

      <ErrorAlert message={error} />

      {loading && (
        <div className="panel">
          <LoadingSkeleton rows={6} />
        </div>
      )}

      {status && !loading && (
        <>
          <div className="panel">
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ margin: 0 }}>Overall</h2>
              <span className={healthy ? 'badge badge-ok' : 'badge badge-warn'}>{healthy ? 'healthy' : 'degraded'}</span>
            </div>
            <p className="meta" style={{ marginTop: 8 }}>
              {status.service} · catalogue currency {status.price_currency}
            </p>
          </div>

          <div className="split-3" style={{ marginTop: '1rem' }}>
            <div className="panel">
              <h2>Database</h2>
              <p className="meta">
                Connected: {yesNo(status.database_connected)}
                <br />
                Products: {fmt(status.db_product_count)}
                <br />
                Catalogue in memory: {fmt(status.catalogue_loaded)}
              </p>
            </div>
            <div className="panel">
              <h2>Indexes</h2>
              <p className="meta">
                BM25 loaded: {yesNo(status.bm25_index_loaded)}
                <br />
                BM25 documents: {fmt(status.bm25_document_count)}
                <br />
                Chroma connected: {yesNo(status.chroma_connected)}
                <br />
                Chroma documents: {fmt(status.chroma_document_count)}
                <br />
                Chroma memory fallback: {yesNo(status.chroma_using_memory_fallback)}
              </p>
            </div>
            <div className="panel">
              <h2>Embeddings</h2>
              <p className="meta">
                Model: {status.embedding_model || 'unavailable'}
                <br />
                Loaded: {yesNo(status.embedding_model_loaded)}
                <br />
                Dimensions: {fmt(status.embedding_dimensions)}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
