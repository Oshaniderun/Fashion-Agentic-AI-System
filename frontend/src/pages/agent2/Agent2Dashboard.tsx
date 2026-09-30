import { Fragment, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  clearSearchHistory,
  deleteSearchHistoryEntry,
  getSearchHistoryEntry,
  listSearchHistory,
} from '../../services/agent2Service';
import { formatPrice, statusMeta } from '../../services/agent2Format';
import { extractErrorMessage } from '../../services/api';
import type { SearchHistoryDetail, SearchHistoryEntry } from '../../types/agent2';

export function Agent2Dashboard() {
  const [entries, setEntries] = useState<SearchHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<'overview' | 'lastjson'>('overview');
  const [openId, setOpenId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SearchHistoryDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [lastEntry, setLastEntry] = useState<SearchHistoryDetail | null>(null);

  useEffect(() => {
    listSearchHistory()
      .then(setEntries)
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const first = entries[0];
    if (!first) {
      setLastEntry(null);
      return;
    }
    let active = true;
    getSearchHistoryEntry(first.id)
      .then((d) => active && setLastEntry(d))
      .catch(() => active && setLastEntry(null));
    return () => {
      active = false;
    };
  }, [entries]);

  const toggle = useCallback(async (id: number) => {
    if (openId === id) {
      setOpenId(null);
      setDetail(null);
      return;
    }
    setOpenId(id);
    setDetail(null);
    setDetailLoading(true);
    try {
      setDetail(await getSearchHistoryEntry(id));
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setDetailLoading(false);
    }
  }, [openId]);

  const remove = async (id: number) => {
    try {
      await deleteSearchHistoryEntry(id);
      setEntries((prev) => prev.filter((e) => e.id !== id));
      if (openId === id) {
        setOpenId(null);
        setDetail(null);
      }
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  const clearAll = async () => {
    try {
      await clearSearchHistory();
      setEntries([]);
      setOpenId(null);
      setDetail(null);
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Retrieval history</h1>
        <p>Your saved searches, across sessions and devices.</p>
      </div>

      {error && <p className="form-error">{error}</p>}

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
          Last retrieval detail
        </button>
      </div>

      {tab === 'lastjson' ? (
        <div className="panel stack">
          <h2 style={{ margin: 0 }}>Last saved retrieval</h2>
          {lastEntry ? (
            <>
              <p className="meta" style={{ margin: 0 }}>
                Actual stored data for{' '}
                <strong style={{ textTransform: 'capitalize' }}>{lastEntry.category}</strong> ·{' '}
                {lastEntry.created_at ? new Date(lastEntry.created_at).toLocaleString() : ''} ·{' '}
                {lastEntry.query_text || 'no query text'}
              </p>
              <pre className="code-block">{JSON.stringify(lastEntry, null, 2)}</pre>
            </>
          ) : (
            <p className="meta">
              {loading ? 'Loading…' : 'No saved searches yet. Use '}
              {!loading && (
                <>
                  <Link to="/agent2/search">Product Search</Link>, or retrieve from an{' '}
                  <Link to="/request">analysis result</Link>.
                </>
              )}
            </p>
          )}
        </div>
      ) : (
        <div className="panel">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0 }}>Saved searches</h2>
            {entries.length > 0 && (
              <button type="button" className="btn btn-ghost" onClick={clearAll}>
                Clear all
              </button>
            )}
          </div>

          {loading ? (
            <p className="meta">Loading…</p>
          ) : entries.length === 0 ? (
            <p className="meta">
              Nothing saved yet. Use <Link to="/agent2/search">Product Search</Link>, or run a{' '}
              <Link to="/request">fashion request</Link> and retrieve from the analysis result —
              searches are stored on the server.
            </p>
          ) : (
            <table style={{ width: '100%', marginTop: 8 }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left' }} className="meta">When</th>
                  <th style={{ textAlign: 'left' }} className="meta">Category</th>
                  <th style={{ textAlign: 'left' }} className="meta">Query</th>
                  <th style={{ textAlign: 'left' }} className="meta">Status</th>
                  <th style={{ textAlign: 'left' }} className="meta">Results</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {entries.map((e) => {
                  const m = statusMeta(e.status, e.relaxed_constraints);
                  const isOpen = openId === e.id;
                  return (
                    <Fragment key={e.id}>
                      <tr>
                        <td className="meta">
                          {e.created_at ? new Date(e.created_at).toLocaleString() : '—'}
                        </td>
                        <td style={{ textTransform: 'capitalize' }}>{e.category ?? '—'}</td>
                        <td className="meta">{e.query_text || '—'}</td>
                        <td>
                          <span className={m.badgeClass}>{m.label}</span>
                        </td>
                        <td>{e.result_count}</td>
                        <td>
                          <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
                            <button type="button" className="chip" onClick={() => void toggle(e.id)}>
                              {isOpen ? 'Hide' : 'View'}
                            </button>
                            <button type="button" className="chip" onClick={() => void remove(e.id)}>
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={6} style={{ paddingTop: 0 }}>
                            <div className="panel" style={{ margin: '4px 0 10px' }}>
                              {detailLoading ? (
                                <p className="meta">Loading…</p>
                              ) : !detail ? (
                                <p className="meta">No details available.</p>
                              ) : (
                                <>
                                  <p className="meta" style={{ margin: 0 }}>
                                    {detail.status === 'no_results'
                                      ? 'Nothing was retrieved for this search.'
                                      : `${detail.products.length} of ${detail.result_count} stored results still listed in the catalogue:`}
                                  </p>
                                  <ul className="stack" style={{ listStyle: 'none', padding: 0, margin: '8px 0 0' }}>
                                    {detail.products.map((p, i) => {
                                      const price = formatPrice(p.price, p.currency ?? 'USD');
                                      return (
                                        <li key={`${p.product_id}-${i}`} className="row" style={{ gap: 8 }}>
                                          <Link to={`/agent2/products/${encodeURIComponent(p.product_id ?? '')}`}>
                                            {p.product_name ?? p.product_id}
                                          </Link>
                                          <span className="meta">{p.brand ?? p.store ?? ''}</span>
                                          <span className="meta">{price ?? 'price not listed'}</span>
                                        </li>
                                      );
                                    })}
                                  </ul>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
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
