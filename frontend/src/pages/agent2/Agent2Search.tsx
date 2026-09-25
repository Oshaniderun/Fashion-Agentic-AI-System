import { useState } from 'react';
import axios from 'axios';
import { ErrorAlert } from '../../components/ErrorAlert';
import { LoadingSkeleton } from '../../components/LoadingSkeleton';
import { ProductCard } from '../../components/ProductCard';
import { agent2Search } from '../../services/agent2Service';
import { recordRecentSearch } from '../../services/agent2History';
import { describeHttpError, statusMeta, validateSearchForm } from '../../services/agent2Format';
import { extractErrorMessage } from '../../services/api';
import type { ProductCategory, RetrievalResponse } from '../../types/agent2';

const CATEGORIES: ProductCategory[] = [
  'top',
  'bottom',
  'dress',
  'outerwear',
  'footwear',
  'accessory',
  'bag',
  'jewelry',
];

function newRequestId(): string {
  return `web-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function Agent2Search() {
  const [category, setCategory] = useState<ProductCategory>('dress');
  const [queryText, setQueryText] = useState('');
  const [colour, setColour] = useState('');
  const [style, setStyle] = useState('');
  const [occasion, setOccasion] = useState('');
  const [maxPrice, setMaxPrice] = useState('50');
  const [topK, setTopK] = useState('5');
  const [result, setResult] = useState<RetrievalResponse | null>(null);
  const [error, setError] = useState('');
  const [fieldError, setFieldError] = useState('');
  const [loading, setLoading] = useState(false);

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const priceNum = maxPrice.trim() === '' ? null : Number(maxPrice);
    const kNum = topK.trim() === '' ? null : Number(topK);
    const invalid = validateSearchForm({ max_price: priceNum, top_k: kNum, query_text: queryText });
    setFieldError(invalid || '');
    if (invalid || priceNum === null || kNum === null) return;

    setLoading(true);
    try {
      const res = await agent2Search({
        request_id: newRequestId(),
        required_category: category,
        query_text: queryText.trim() || null,
        preferred_colour: colour.trim() || null,
        style: style.trim() || null,
        occasion: occasion.trim() || null,
        max_price: priceNum,
        top_k: kNum,
      });
      setResult(res);
      recordRecentSearch({
        at: new Date().toISOString(),
        category,
        query_text: queryText.trim() || null,
        status: res.status,
        results: res.results.length,
        response: res,
      });
    } catch (err) {
      setResult(null);
      setError(
        axios.isAxiosError(err) && err.response ? describeHttpError(err.response.status) : extractErrorMessage(err)
      );
    } finally {
      setLoading(false);
    }
  };

  const meta = result ? statusMeta(result.status, result.relaxed_constraints) : null;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Product search</h1>
        <p>Hybrid retrieval over the live catalogue (BM25 + semantic + hard filters + relaxation ladder).</p>
      </div>

      <div className="panel">
        <form className="stack" onSubmit={runSearch}>
          <div className="split-3">
            <div className="field">
              <label htmlFor="cat">Required category</label>
              <select id="cat" value={category} onChange={(e) => setCategory(e.target.value as ProductCategory)}>
                {CATEGORIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="price">Price ceiling (USD, &gt; 0)</label>
              <input
                id="price"
                type="number"
                min="0.01"
                step="0.01"
                value={maxPrice}
                onChange={(e) => setMaxPrice(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="topk">Results (top_k, 1–20)</label>
              <input id="topk" type="number" min="1" max="20" step="1" value={topK} onChange={(e) => setTopK(e.target.value)} />
            </div>
          </div>

          <div className="field">
            <label htmlFor="query">Query text</label>
            <input
              id="query"
              placeholder="e.g. black elegant evening dress"
              value={queryText}
              onChange={(e) => setQueryText(e.target.value)}
            />
          </div>

          <div className="split-3">
            <div className="field">
              <label htmlFor="colour">Preferred colour</label>
              <input id="colour" value={colour} onChange={(e) => setColour(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="style">Style (hard filter)</label>
              <input id="style" placeholder="e.g. elegant" value={style} onChange={(e) => setStyle(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="occasion">Occasion</label>
              <input id="occasion" value={occasion} onChange={(e) => setOccasion(e.target.value)} />
            </div>
          </div>

          {fieldError && <ErrorAlert message={fieldError} />}

          <div className="row">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              {loading ? 'Searching…' : 'Search products'}
            </button>
          </div>
        </form>
      </div>

      <ErrorAlert message={error} />

      {loading && (
        <div className="panel" style={{ marginTop: '1rem' }}>
          <LoadingSkeleton rows={5} />
        </div>
      )}

      {result && !loading && (
        <div className="panel" style={{ marginTop: '1rem' }}>
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
            <h2 style={{ margin: 0 }}>
              {result.results.length} result{result.results.length === 1 ? '' : 's'}
            </h2>
            <span className={meta!.badgeClass}>{meta!.label}</span>
          </div>
          <p className="meta">{meta!.message}</p>
          {result.relaxed_constraints.length > 0 && (
            <div className="chip-row">
              {result.relaxed_constraints.map((r) => (
                <span key={r} className="badge badge-muted">
                  relaxed: {r}
                </span>
              ))}
            </div>
          )}
          {result.notes && <p className="meta">Note: {result.notes}</p>}

          {result.results.length === 0 ? (
            <p className="meta" style={{ marginTop: 8 }}>
              The service returned no products for these constraints.
            </p>
          ) : (
            <div className="wardrobe-grid" style={{ marginTop: 12 }}>
              {result.results.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
