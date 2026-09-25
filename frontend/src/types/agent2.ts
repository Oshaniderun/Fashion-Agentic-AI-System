// Agent 2 (Fashion Information Retrieval) TypeScript contracts.
// Mirrors shared/schemas/agent2_schemas.py and the ops adapter in
// agents/agent2_retrieval/app/api/ops_routes.py. The backend is the single
// source of truth; this file must stay in sync with those Pydantic models.

export type ProductCategory =
  | 'top'
  | 'bottom'
  | 'dress'
  | 'outerwear'
  | 'footwear'
  | 'accessory'
  | 'bag'
  | 'jewelry';

// RetrievalStatus — set by Agent 2's decision logic (relaxation ladder).
export type RetrievalStatus = 'ok' | 'relaxed' | 'low_confidence' | 'no_results';

// RetrievalRequest — mirrors the Pydantic model. request_id, required_category
// and max_price are required; max_price must be > 0; top_k is 1..20.
export interface RetrievalRequest {
  request_id: string;
  required_category: ProductCategory;
  preferred_colour?: string | null;
  style?: string | null;
  occasion?: string | null;
  query_text?: string | null;
  max_price: number;
  top_k?: number;
  is_retry?: boolean;
  retry_count?: number;
  excluded_product_ids?: string[];
}

// ScoreBreakdown — sub-scores behind the weighted relevance formula.
// The frontend displays these as-is and NEVER recomputes relevance client-side.
export interface ScoreBreakdown {
  semantic_similarity: number;
  colour_match: number;
  style_match: number;
  budget_suitability: number;
  availability: number;
}

// ProductResult — one retrieved/ranked catalogue product.
// Nulls are honest (colour may be "Unknown"; price/url may be null). Never
// substitute 0, a fake URL, or a fabricated price.
export interface ProductResult {
  product_id: string;
  name: string;
  category: ProductCategory;
  colour?: string | null;
  price?: number | null;
  store: string;
  url?: string | null;
  availability: boolean;
  relevance_score: number;
  score_breakdown: ScoreBreakdown;
}

export interface RetrievalResponse {
  request_id: string;
  status: RetrievalStatus;
  results: ProductResult[];
  relaxed_constraints: string[];
  notes?: string | null;
}

// ---- GET /api/v1/status ----
// Every field may be null when the backend probe fails; the UI must show an
// honest "unavailable" rather than a fabricated green.
export interface Agent2Status {
  service: string;
  database_connected: boolean;
  db_product_count: number | null;
  catalogue_loaded: number;
  bm25_index_loaded: boolean;
  bm25_document_count: number | null;
  chroma_connected: boolean;
  chroma_using_memory_fallback: boolean | null;
  chroma_document_count: number | null;
  embedding_model: string | null;
  embedding_model_loaded: boolean | null;
  embedding_dimensions: number | null;
  price_currency: string;
}

// ---- POST /api/v1/search/agent1-handoff ----
export interface CategoryRetrieval {
  category: string;
  request: RetrievalRequest | null;
  response: RetrievalResponse | null;
  error: string | null;
}

export interface HandoffRetrievalResponse {
  request_id: string;
  price_ceiling_used: number;
  price_currency: string;
  warnings: string[];
  retrievals: CategoryRetrieval[];
}

// ---- GET /api/v1/products/{id} (app/schemas/product.py) ----
export interface Agent2Product {
  product_id: string;
  product_name: string;
  category?: string | null;
  subcategory?: string | null;
  brand?: string | null;
  price?: number | null;
  currency?: string | null;
  colour?: string | null;
  material?: string | null;
  style?: string | null;
  size?: string | null;
  description?: string | null;
  store?: string | null;
  image_url?: string | null;
  product_url?: string | null;
  availability?: boolean | null;
  created_at: string;
}
