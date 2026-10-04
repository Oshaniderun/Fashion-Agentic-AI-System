import { api } from './api';
import type { Agent1OutputContract } from '../types';
import type { RetrievalRequest, RetrievalResponse } from '../types/agent2';
import type {
  AffiliateClickResult,
  BudgetOptimizationResponse,
  ComparisonRow,
  OutfitOption,
  UsageStats,
} from '../types/budget';

// All calls go through the shared axios instance (which attaches the user's
// JWT). The Vite dev proxy routes /budget to the budget service on port 8003.
// The inter-agent service token is never used or stored here.

export interface PlanPurchasesPayload {
  agent1_output: Agent1OutputContract;
  retrieval_by_category: Record<string, RetrievalResponse>;
  retrieval_requests_by_category?: Record<string, RetrievalRequest> | null;
  user_id?: number | string | null;
  strategy_preference?: string;
  enable_feedback_loop?: boolean;
}

export async function planPurchases(
  payload: PlanPurchasesPayload,
  llmPolish = false
): Promise<BudgetOptimizationResponse> {
  const { data } = await api.post<BudgetOptimizationResponse>(
    `/budget/plan-purchases${llmPolish ? '?llm_polish=true' : ''}`,
    payload
  );
  return data;
}

export interface ComparisonResult {
  ranked_options: ComparisonRow[];
  category_breakdown: { categories: unknown[]; all_products?: unknown[]; summary?: string };
  savings_ranking: Record<string, unknown>[];
  summary_stats: Record<string, unknown>;
}

export async function compareOptions(
  options: OutfitOption[],
  budget: number
): Promise<ComparisonResult> {
  const { data } = await api.post<ComparisonResult>('/budget/compare-options', {
    options,
    budget,
  });
  return data;
}

export async function getUsage(userId: string | number): Promise<UsageStats> {
  const { data } = await api.get<UsageStats>(`/budget/usage/${encodeURIComponent(String(userId))}`);
  return data;
}

export interface UpgradeResult {
  user_id: string;
  tier: 'free' | 'premium';
  message: string;
  monthly_limit: number; // -1 = unlimited
}

export async function upgradeToPremium(userId: string): Promise<UpgradeResult> {
  const { data } = await api.post<UpgradeResult>('/budget/subscription/upgrade', {
    user_id: userId,
  });
  return data;
}

export interface AffiliateClickRow {
  product_id: string;
  product_name?: string | null;
  product_url?: string | null;
  store?: string | null;
  category?: string | null;
  price_usd?: number | null;
  estimated_commission_usd?: number | null;
  clicked_at: string;
}

export async function getAffiliateHistory(
  userId: string | number,
  limit = 20
): Promise<{ user_id: string; clicks: AffiliateClickRow[] }> {
  const { data } = await api.get(
    `/budget/affiliate/history/${encodeURIComponent(String(userId))}?limit=${limit}`
  );
  return data;
}

export async function clearAffiliateHistory(
  userId: string | number
): Promise<{ user_id: string; cleared: number }> {
  const { data } = await api.delete(
    `/budget/affiliate/history/${encodeURIComponent(String(userId))}`
  );
  return data;
}

export async function trackProductClick(payload: {
  product_id: string;
  product_name?: string | null;
  product_url?: string | null;
  store?: string | null;
  category?: string | null;
  price_usd?: number | null;
  request_id?: string | null;
  user_id?: string | null;
}): Promise<AffiliateClickResult> {
  const { data } = await api.post<AffiliateClickResult>('/budget/affiliate/track-click', payload);
  return data;
}

export async function budgetHealth(): Promise<{
  status: string;
  service: string;
  version: string;
  currency: string;
  llm: string;
  db: string;
}> {
  const { data } = await api.get('/budget/health');
  return data;
}
