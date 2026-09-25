import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { readRecentSearches, type RecentSearch } from '../../services/agent2History';
import { statusMeta } from '../../services/agent2Format';

export function Agent2Dashboard() {
  const [recent, setRecent] = useState<RecentSearch[]>([]);
  const [tab, setTab] = useState<'overview' | 'lastjson'>('overview');

  useEffect(() => {
    setRecent(readRecentSearches());
  }, []);

  const lastWithResponse = recent.find((r) => r.response !== undefined);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Retrieval history</h1>
        <p>Searches from this browser session.</p>
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
          className={`chip ${tab === 'lastjson' ? 'active' : ''}`}
          onClick={() => setTab('lastjson')}
        >
          Last retrieval JSON
        </button>
      </div>

      {tab === 'lastjson' ? (
        <div className="panel stack">
          <h2 style={{ margin: 0 }}>Last retrieval result</h2>
          {lastWithResponse ? (
            <>
              <p className="meta" style={{ margin: 0 }}>
                Actual response from{' '}
                <strong style={{ textTransform: 'capitalize' }}>{lastWithResponse.category}</strong> ·{' '}
                {new Date(lastWithResponse.at).toLocaleTimeString()} ·{' '}
                {lastWithResponse.query_text || 'no query text'}
              </p>
              <pre className="code-block">{JSON.stringify(lastWithResponse.response, null, 2)}</pre>
            </>
          ) : (
            <p className="meta">
              No retrieval has run in this session yet. Use{' '}
              <Link to="/agent2/search">Product Search</Link>, or retrieve from an{' '}
              <Link to="/request">analysis result</Link>.
            </p>
          )}
        </div>
      ) : (
        <div className="panel">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0 }}>Recent searches</h2>
            <Link to="/agent2/history" className="btn btn-ghost">
              About history
            </Link>
          </div>
          <p className="meta">
            Real searches you ran in this browser session (up to 20). This list disappears when the tab closes.
          </p>
          {recent.length === 0 ? (
            <p className="meta">
              No searches yet in this session. Use{' '}
              <Link to="/agent2/search">Product Search</Link>, or run a{' '}
              <Link to="/request">fashion request</Link> and retrieve from the analysis result.
            </p>
          ) : (
            <table style={{ width: '100%', marginTop: 8 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }} className="meta">
                    Time
                  </th>
                  <th style={{ textAlign: 'left' }} className="meta">
                    Category
                  </th>
                  <th style={{ textAlign: 'left' }} className="meta">
                    Query
                  </th>
                  <th style={{ textAlign: 'left' }} className="meta">
                    Status
                  </th>
                  <th style={{ textAlign: 'left' }} className="meta">
                    Results
                  </th>
                </tr>
              </thead>
              <tbody>
                {recent.map((r, i) => {
                  const m = statusMeta(r.status);
                  return (
                    <tr key={`${r.at}-${i}`}>
                      <td className="meta">{new Date(r.at).toLocaleTimeString()}</td>
                      <td style={{ textTransform: 'capitalize' }}>{r.category}</td>
                      <td className="meta">{r.query_text || '—'}</td>
                      <td>
                        <span className={m.badgeClass}>{m.label}</span>
                      </td>
                      <td>{r.results}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
