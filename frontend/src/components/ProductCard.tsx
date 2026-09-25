import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import type { ProductResult } from '../types/agent2';
import { cleanText, formatPrice, formatScore } from '../services/agent2Format';

interface Props {
  product: ProductResult;
  currency?: string;
}

const BREAKDOWN_LABELS: Record<keyof ProductResult['score_breakdown'], string> = {
  semantic_similarity: 'Semantic similarity',
  colour_match: 'Colour match',
  style_match: 'Style match',
  budget_suitability: 'Budget suitability',
  availability: 'Availability',
};

export function ProductCard({ product, currency = 'USD' }: Props) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const price = formatPrice(product.price, currency);
  const colour = cleanText(product.colour);
  const relevance = formatScore(product.relevance_score);

  return (
    <div className="wardrobe-card" style={{ cursor: 'default' }}>
      <div className="body" style={{ position: 'relative' }}>
        {/* Backend-calculated score only. Labelled "Retrieval relevance",
            never "AI confidence", and never recomputed here. */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? 'Hide why this product was retrieved' : 'Show why this product was retrieved'}
          title={open ? 'Hide why this product was retrieved' : 'Show why this product was retrieved'}
          style={{
            position: 'absolute',
            top: 10,
            right: 10,
            zIndex: 1,
            width: 22,
            height: 22,
            padding: 0,
            borderRadius: '50%',
            border: '1px solid currentColor',
            background: open ? 'rgba(0,0,0,0.08)' : 'transparent',
            color: 'inherit',
            font: 'italic 600 13px Georgia, serif',
            lineHeight: '20px',
            textAlign: 'center',
            cursor: 'pointer',
          }}
        >
          i
        </button>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span className="badge badge-muted" style={{ textTransform: 'capitalize' }}>
            {product.category}
          </span>
          <span className="badge badge-ok" style={{ marginRight: 30 }} title="Weighted score from Agent 2 retrieval">
            Retrieval relevance: {relevance ?? 'n/a'}
          </span>
        </div>

        <h3 style={{ marginTop: 8 }}>{product.name}</h3>
        <p className="meta">
          {colour ? (
            <>
              Colour: {colour}
              <br />
            </>
          ) : (
            <>
              Colour: not listed
              <br />
            </>
          )}
          Price: {price ?? 'not listed'}
          <br />
          Store: {product.store || 'not listed'} · {product.availability ? 'Available' : 'Not available'}
        </p>

        <div className="meter" aria-hidden>
          <span style={{ width: `${Math.round((product.relevance_score || 0) * 100)}%` }} />
        </div>

        <div className="row" style={{ marginTop: 10, gap: 8, flexWrap: 'wrap' }}>
          <Link
            className="btn btn-secondary"
            to={{
              pathname: `/agent2/products/${encodeURIComponent(product.product_id)}`,
              search: `from=${encodeURIComponent(location.pathname)}`,
            }}
          >
            Details
          </Link>
          {product.url ? (
            <a className="btn btn-ghost" href={product.url} target="_blank" rel="noreferrer noopener">
              Open listing
            </a>
          ) : null}
        </div>

        {open && (
          <div className="stack" style={{ marginTop: 8 }}>
            {(Object.keys(BREAKDOWN_LABELS) as (keyof ProductResult['score_breakdown'])[]).map((key) => {
              const value = product.score_breakdown[key];
              return (
                <div key={key} className="stack" style={{ gap: 2 }}>
                  <span className="meta">
                    {BREAKDOWN_LABELS[key]}: {formatScore(value) ?? 'n/a'}
                  </span>
                  <div className="meter" aria-hidden>
                    <span style={{ width: `${Math.round((value || 0) * 100)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
