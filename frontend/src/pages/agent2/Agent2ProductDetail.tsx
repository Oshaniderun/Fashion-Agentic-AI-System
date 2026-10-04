import { useEffect, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ShoppingBag } from 'lucide-react';
import { ErrorAlert } from '../../components/ErrorAlert';
import { LoadingSkeleton } from '../../components/LoadingSkeleton';
import { useAuth } from '../../context/AuthContext';
import { getAgent2Product } from '../../services/agent2Service';
import { describeHttpError } from '../../services/agent2Format';
import { storeUrl } from '../../services/budgetFormat';
import { trackProductClick } from '../../services/budgetService';
import { extractErrorMessage, imageUrl } from '../../services/api';
import type { Agent2Product } from '../../types/agent2';

function Row({ label, value }: { label: string; value: string | number | boolean | null | undefined }) {
  let shown: string;
  if (value === null || value === undefined || value === '') shown = 'not listed';
  else if (typeof value === 'boolean') shown = value ? 'yes' : 'no';
  else shown = String(value);
  return (
    <p className="meta" style={{ margin: '4px 0' }}>
      <strong>{label}:</strong> {shown}
    </p>
  );
}

export function Agent2ProductDetail() {
  const { productId } = useParams();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const origin = searchParams.get('from');
  // Return to the page that linked here (e.g. the analysis result list) when known.
  const fromValid = !!origin && origin.startsWith('/') && !origin.startsWith('//');
  const backTo = fromValid ? (origin as string) : '/agent2/search';
  const backLabel = fromValid ? 'Back to results' : 'Back to search';
  const [product, setProduct] = useState<Agent2Product | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!productId) return;
    setLoading(true);
    setError('');
    getAgent2Product(productId)
      .then((p) => setProduct(p))
      .catch((err) => {
        setProduct(null);
        setError(
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          (err as any)?.response ? describeHttpError((err as any).response.status) : extractErrorMessage(err)
        );
      })
      .finally(() => setLoading(false));
  }, [productId]);

  if (loading) {
    return (
      <div className="page">
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  if (!product) {
    return (
      <div className="page">
        <ErrorAlert message={error || 'Product not found'} />
        <Link to={backTo} className="btn btn-primary">
          {backLabel}
        </Link>
      </div>
    );
  }

  const img = imageUrl(product.image_url);
  const listingUrl = storeUrl(product.product_id, product.product_url);
  // Only a visit that came from a plan can attribute the click to one.
  const planRequestId = origin?.startsWith('/budget/')
    ? decodeURIComponent(origin.slice('/budget/'.length))
    : null;

  const openListing = async () => {
    if (!listingUrl) return;
    try {
      await trackProductClick({
        product_id: product.product_id,
        product_name: product.product_name,
        product_url: listingUrl,
        store: product.store ?? null,
        category: product.category ?? null,
        price_usd: product.price ?? null,
        request_id: planRequestId,
        user_id: user?.id != null ? String(user.id) : undefined,
      });
    } catch {
      /* tracking is best-effort; the user still gets their link */
    }
    window.open(listingUrl, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1 style={{ textTransform: 'none' }}>{product.product_name}</h1>
        <p>
          Catalogue product <code>{product.product_id}</code>
        </p>
      </div>

      <div className="split-2">
        <div className="panel">
          <h2>Details</h2>
          <Row label="Category" value={product.category} />
          <Row label="Subcategory" value={product.subcategory} />
          <Row label="Brand" value={product.brand} />
          <Row label="Colour" value={product.colour} />
          <Row label="Material" value={product.material} />
          <Row label="Style" value={product.style} />
          <Row label="Size" value={product.size} />
          <Row
            label="Price"
            value={product.price === null || product.price === undefined ? null : `${product.currency || ''} ${product.price}`.trim()}
          />
          <Row label="Store" value={product.store} />
          <Row label="Availability" value={product.availability} />
          {product.description && (
            <p className="meta" style={{ marginTop: 10 }}>
              <strong>Description:</strong>
              <br />
              {product.description}
            </p>
          )}
          {listingUrl ? (
            <div className="row" style={{ marginTop: 12 }}>
              <button type="button" className="btn btn-secondary" onClick={() => void openListing()}>
                <ShoppingBag size={14} /> View listing
              </button>
            </div>
          ) : (
            <p className="meta" style={{ marginTop: 10 }}>
              No direct listing link for this product.
            </p>
          )}
          <div className="row" style={{ marginTop: 12 }}>
            <Link to={backTo} className="btn btn-ghost">
              {backLabel}
            </Link>
          </div>
        </div>

        <div className="panel">
          <h2>Image</h2>
          {img ? (
            <img src={img} alt={product.product_name} style={{ width: '100%', borderRadius: 12, objectFit: 'contain' }} />
          ) : (
            <p className="meta">No image available for this product.</p>
          )}
        </div>
      </div>
    </div>
  );
}
