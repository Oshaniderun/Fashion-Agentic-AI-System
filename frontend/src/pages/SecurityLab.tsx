import { useEffect, useState } from 'react';
import { ErrorAlert } from '../components/ErrorAlert';
import { listSecurityPresets, testPromptInjection } from '../services/agentService';
import { extractErrorMessage } from '../services/api';
import type { PresetAttack, SecurityThreatReport } from '../types';

export function SecurityLab() {
  const [presets, setPresets] = useState<PresetAttack[]>([]);
  const [prompt, setPrompt] = useState('');
  const [report, setReport] = useState<SecurityThreatReport | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listSecurityPresets()
      .then((data) => {
        setPresets(data);
        if (data[0]) setPrompt(data[0].prompt);
      })
      .catch((err) => setError(extractErrorMessage(err)));
  }, []);

  const runTest = async () => {
    setLoading(true);
    setError('');
    try {
      const result = await testPromptInjection(prompt);
      setReport(result);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Security Lab</h1>
        <p>
          Developer testbed for prompt injection. User input is treated as data — this page never exposes real
          secrets.
        </p>
      </div>

      <ErrorAlert message={error} />

      <div className="split-2">
        <div className="panel stack">
          <h2>Preset attack payloads</h2>
          <div className="chip-row">
            {presets.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`chip ${prompt === p.prompt ? 'active' : ''}`}
                onClick={() => setPrompt(p.prompt)}
              >
                {p.name}
              </button>
            ))}
          </div>
          <div className="field">
            <label>Test prompt</label>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={5} />
          </div>
          <button className="btn btn-primary" type="button" onClick={runTest} disabled={loading || !prompt}>
            {loading ? 'Evaluating…' : 'Test defense'}
          </button>
        </div>

        <div className="panel stack">
          <h2>Defense response</h2>
          {!report ? (
            <p className="meta">Run a payload to see sanitization and risk scoring.</p>
          ) : (
            <>
              <span className={`badge ${report.is_safe ? 'badge-ok' : 'badge-danger'}`}>
                {report.defensive_action} · risk {Math.round(report.risk_score * 100)}%
              </span>
              {report.attack_category && (
                <p>
                  Category: <strong>{report.attack_category}</strong>
                </p>
              )}
              <p>{report.explanation}</p>
              {report.detected_indicators.length > 0 && (
                <div className="chip-row">
                  {report.detected_indicators.map((d) => (
                    <span key={d} className="badge badge-warn">
                      {d}
                    </span>
                  ))}
                </div>
              )}
              <div>
                <div className="meta">Sanitized input</div>
                <pre className="code-block">{report.sanitized_input}</pre>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
