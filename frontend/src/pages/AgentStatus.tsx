import { useEffect, useState } from 'react';
import { ErrorAlert } from '../components/ErrorAlert';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { agentAnalyze, getAgentSchema, getAgentStatus, getHealth } from '../services/agentService';
import { extractErrorMessage } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { API_DOCS_URL } from '../config';
import type { Agent1OutputContract, AgentStatus } from '../types';

export function AgentStatusPage() {
  const { user } = useAuth();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [schema, setSchema] = useState<Record<string, unknown> | null>(null);
  const [health, setHealth] = useState<string>('');
  const [simResult, setSimResult] = useState<Agent1OutputContract | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);

  useEffect(() => {
    Promise.all([getAgentStatus(), getAgentSchema(), getHealth()])
      .then(([s, sc, h]) => {
        setStatus(s);
        setSchema(sc);
        setHealth(h.status);
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  const runSimulator = async () => {
    setSimulating(true);
    setError('');
    try {
      const result = await agentAnalyze({
        user_id: user?.id,
        query_text:
          "I need something elegant but not too formal for my cousin's engagement. I don't want bright colours.",
      });
      setSimResult(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSimulating(false);
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
        <h1>Agent Status</h1>
        <p>Health, capabilities, and the JSON contract future agents consume.</p>
      </div>
      <ErrorAlert message={error} />

      <div className="split-3">
        <div className="panel">
          <h2>Health</h2>
          <span className={`badge ${health === 'ok' || status?.status === 'healthy' ? 'badge-ok' : 'badge-warn'}`}>
            {status?.status || health || 'unknown'}
          </span>
          <p className="meta" style={{ marginTop: 8 }}>
            {status?.agent}
            <br />
            Version {status?.version}
          </p>
        </div>
        <div className="panel">
          <h2>Backends</h2>
          <p className="meta">
            Env: {status?.backend}
            <br />
            Vision: {status?.vision_backend}
            <br />
            LLM: {status?.llm_provider}
            <br />
            Demo seed: {status?.seed_demo_data ? 'on' : 'off'}
          </p>
        </div>
        <div className="panel">
          <h2>OpenAPI</h2>
          <a className="btn btn-secondary" href={API_DOCS_URL} target="_blank" rel="noreferrer">
            Open Swagger
          </a>
        </div>
      </div>

      <div className="panel" style={{ marginTop: '1rem' }}>
        <h2>Capabilities</h2>
        <div className="chip-row">
          {(status?.capabilities || []).map((c) => (
            <span key={c} className="badge badge-muted">
              {c}
            </span>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginTop: '1rem' }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0 }}>Contract simulator</h2>
          <button className="btn btn-primary" type="button" onClick={runSimulator} disabled={simulating}>
            {simulating ? 'Running…' : 'POST /api/agent/analyze'}
          </button>
        </div>
        <p className="meta">
          Calls the inter-agent endpoint with your JWT for user #{user?.id}. No demo-user fallback.
        </p>
        {simResult && <pre className="code-block">{JSON.stringify(simResult, null, 2)}</pre>}
      </div>

      <div className="panel" style={{ marginTop: '1rem' }}>
        <h2>Schema explorer</h2>
        <pre className="code-block">{JSON.stringify(schema, null, 2)}</pre>
      </div>
    </div>
  );
}
