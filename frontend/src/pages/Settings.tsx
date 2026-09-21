import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { getAgentStatus } from '../services/agentService';
import { ErrorAlert } from '../components/ErrorAlert';
import { extractErrorMessage } from '../services/api';
import type { AgentStatus } from '../types';

export function Settings() {
  const { user } = useAuth();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    getAgentStatus()
      .then(setStatus)
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Settings</h1>
        <p>Profile, AI backend info, and privacy notes for this prototype.</p>
      </div>
      <ErrorAlert message={error} />

      <div className="split-2">
        <div className="panel stack">
          <h2>Profile</h2>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="meta">Name</span>
            <strong>{user?.name}</strong>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="meta">Email</span>
            <strong>{user?.email}</strong>
          </div>
          <p className="meta">
            Use Register on the sign-in screen to create an account. Passwords are hashed; JWTs expire after the
            configured window.
          </p>
        </div>

        <div className="panel stack">
          <h2>AI preferences</h2>
          <p className="meta">
            Vision backend: <strong>{status?.vision_backend || '—'}</strong>
            <br />
            LLM provider: <strong>{status?.llm_provider || '—'}</strong>
            <br />
            Configured via environment variables — never hardcoded API keys.
          </p>
        </div>
      </div>

      <div className="panel" style={{ marginTop: '1rem' }}>
        <h2>Data & privacy</h2>
        <ul className="meta">
          <li>Wardrobe images are stored locally under the Agent 1 uploads directory.</li>
          <li>Items are scoped to your user account; other users cannot access them.</li>
          <li>You can delete wardrobe items at any time from the wardrobe page.</li>
          <li>Passwords are hashed with bcrypt; JWTs expire after the configured window.</li>
          <li>Agent 1 does not infer race, body shape, attractiveness, or gender identity from images.</li>
        </ul>
      </div>
    </div>
  );
}
