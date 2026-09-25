import { Link } from 'react-router-dom';

export function Agent2History() {
  return (
    <div className="page">
      <div className="page-header">
        <h1>Agent 2 · About search history</h1>
        <p>Why there is no server-side history, and what the dashboard list actually is.</p>
      </div>

      <div className="panel">
        <span className="badge badge-warn">Not currently persisted</span>
        <p className="meta" style={{ marginTop: 10 }}>
          Agent 2 does not expose a search-history endpoint, and the frontend intentionally does not fake
          one or store results locally. Every search is computed live against the catalogue. The{' '}
          <Link to="/agent2">Agent 2 dashboard</Link> lists the searches you ran in the current browser
          session only — that list is held in this tab and disappears when it closes.
        </p>
        <p className="meta">
          When the backend adds durable history, this page will list past requests, their status
          (ok / relaxed / low_confidence / no_results), and the retrieved products.
        </p>
        <div className="row" style={{ marginTop: 12 }}>
          <Link to="/agent2/search" className="btn btn-primary">
            Run a search
          </Link>
        </div>
      </div>
    </div>
  );
}
