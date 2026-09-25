// Budget & purchase planning TypeScript contracts.
// Mirrors shared/schemas/agent3_schemas.py. The backend is the single source
// of truth; the frontend displays these values as-is and never recomputes
// money math client-side. All amounts are USD.

import type {
  Agent1OutputContract,
  Agent2SearchRequirement,
  WardrobeSummaryItem,
} from './index';
import type { RetrievalRequest, RetrievalResponse } from './agent2';

export type OptimizationStrategy =
  | 'buy_nothing'
  | 'best_value'
  | 'top_match'
  | 'minimal_purchase'
  | 'all';

export type BudgetStatus =
  | 'within_budget'
  | 'exceeds_budget'
  | 'partially_feasible'
  | 'no_purchase_needed';

export type BudgetSource = 'user_stated' | 'search_ceiling';

export interface CandidateProductItem {
  product_id: string;
  name: string;
  category: string;
  colour?: string | null;
  price: number;
  store?: string | null;
  url?: string | null;
  relevance_score: number;
  availability: boolean;
}

export interface WardrobeRepurposedItem {
  wardrobe_id: string;
  category: string;
  type: string;
  colour: string;
  repurpose_role: string;
  cost: number;
}

export interface CostBreakdown {
  total_cost: number;
  budget_ceiling: number;
  budget_remaining: number;
  savings_amount: number;
  savings_percentage: number;
  cost_per_category: Record<string, number>;
}

export interface OutfitOption {
  combination_id: string;
  strategy: OptimizationStrategy;
  name: string;
  description: string;
  selected_products: CandidateProductItem[];
  wardrobe_items_used: WardrobeRepurposedItem[];
  cost_breakdown: CostBreakdown;
  budget_efficiency_score: number;
  relevance_score: number;
  overall_value_score: number;
  is_within_budget: boolean;
  financial_explanation: string;
}

export interface FeedbackLoopRecommendation {
  category: string;
  current_lowest_price: number;
  target_max_price: number;
  action: string;
  suggested_query_notes?: string | null;
}

export interface RetrievalRetryLog {
  iteration: number;
  category: string;
  target_max_price: number;
  previous_lowest_price: number;
  new_products_found: number;
  notes?: string | null;
}

export interface BudgetOptimizationResponse {
  request_id: string;
  status: BudgetStatus;
  budget_ceiling: number;
  budget_source: BudgetSource;
  options: OutfitOption[];
  recommended_option_id?: string | null;
  buy_nothing_available: boolean;
  cheapest_combination_cost?: number | null;
  feedback_loop_recommendations: FeedbackLoopRecommendation[];
  retry_log: RetrievalRetryLog[];
  notes?: string | null;
}

export interface PlanPurchasesRequest {
  agent1_output: Agent1OutputContract;
  retrieval_by_category: Record<string, RetrievalResponse>;
  retrieval_requests_by_category?: Record<string, RetrievalRequest> | null;
  user_id?: string | number | null;
  strategy_preference?: OptimizationStrategy;
  enable_feedback_loop?: boolean;
}

export interface UsageStats {
  user_id: string;
  month: string;
  tier: 'free' | 'premium';
  recommendations_used: number;
  monthly_limit: number; // -1 = unlimited
  recommendations_remaining: number; // -1 = unlimited
  upgraded_at?: string | null;
  premium_price_usd: number;
  premium_benefits: string[];
}

export interface AffiliateClickResult {
  click_id: number;
  product_id: string;
  tracked_url: string;
  estimated_commission_usd?: number | null;
  message: string;
}

export interface ComparisonRow {
  rank: number;
  option_id: string;
  strategy: string;
  name: string;
  total_cost_usd: number;
  budget_usd: number;
  savings_usd: number;
  savings_pct: number;
  budget_remaining_usd: number;
  within_budget: boolean;
  n_new_items: number;
  n_wardrobe_reused: number;
  // Comparison rows come back with scores already scaled to 0..100 (percent).
  relevance_score: number;
  budget_efficiency: number;
  overall_value_score: number;
  items_purchased: string;
  stores: string;
  [key: string]: unknown;
}

export interface ComparisonResult {
  ranked_options: ComparisonRow[];
  category_breakdown: Record<string, unknown>;
  savings_ranking: Record<string, unknown>[];
  summary_stats: Record<string, unknown>;
}
