// Outfit decision TypeScript contracts.
// Mirrors shared/schemas/agent4_schemas.py. The backend is the single source
// of truth; the frontend displays these values as-is and never recomputes
// money math or the decision client-side. All amounts are USD.

import type { Agent1OutputContract } from './index';
import type { RetrievalResponse } from './agent2';
import type { BudgetOptimizationResponse } from './budget';

export type DecisionStatus =
  | 'complete'
  | 'partial'
  | 'no_suitable_outfit'
  | 'insufficient_input';

export type ConfidenceLevel = 'high' | 'medium' | 'low';

export type PieceSource = 'wardrobe' | 'purchase';

export interface DecisionRequest {
  request_id: string;
  agent1_output: Agent1OutputContract;
  budget_response: BudgetOptimizationResponse;
  retrieval_by_category: Record<string, RetrievalResponse>;
  user_id?: string | number | null;
  prefer_minimal_purchases?: boolean;
}

export interface OutfitPiece {
  source: PieceSource;
  item_id: string;
  category: string;
  name: string;
  colour?: string | null;
  type?: string | null;
  price_usd?: number | null;
  store?: string | null;
  url?: string | null;
  availability?: boolean | null;
  relevance_score?: number | null;
  role: string;
}

export interface BudgetOutcome {
  maximum_usd: number;
  additional_cost_usd: number;
  remaining_usd: number;
  within_budget: boolean;
}

export interface PurchaseSummary {
  purchase_count: number;
  existing_items_used: number;
}

export interface AlternativeOutfit {
  combination_id: string;
  strategy: string;
  name: string;
  total_cost_usd: number;
  within_budget: boolean;
  decision_score: number;
  reason: string;
}

export interface DecisionOutcome {
  status: DecisionStatus;
  confidence_score: number;
  confidence_level: ConfidenceLevel;
}

export interface ValidationIssue {
  severity: 'error' | 'warning';
  code: string;
  message: string;
  product_id?: string | null;
  field?: string | null;
}

export interface CandidateMetrics {
  occasion_fit: number;
  style_fit: number;
  colour_fit: number;
  wardrobe_reuse: number;
  retrieval_relevance: number;
  budget_efficiency: number;
  purchase_count: number;
  within_budget: boolean;
  is_complete: boolean;
  decision_score: number;
}

export interface DecisionResponse {
  request_id: string;
  decision: DecisionOutcome;
  selected_combination_id?: string | null;
  strategy?: string | null;
  outfit: OutfitPiece[];
  budget: BudgetOutcome;
  purchase_summary: PurchaseSummary;
  metrics?: CandidateMetrics | null;
  alternatives: AlternativeOutfit[];
  unresolved_requirements: string[];
  explanation: string;
  validation_issues: ValidationIssue[];
  currency: string;
}
