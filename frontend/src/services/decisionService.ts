import { api } from './api';
import { readCachedPlan, readRetrievalContext } from './budgetHistory';
import type { FashionAnalysisResponse, Agent1OutputContract } from '../types';
import type { RetrievalResponse } from '../types/agent2';
import type { BudgetOptimizationResponse } from '../types/budget';
import type { DecisionRequest, DecisionResponse } from '../types/decision';

// All calls go through the shared axios instance (which attaches the user's
// JWT). The Vite dev proxy routes /decision to the decision service on port
// 8004. The inter-agent service token is never used or stored here.

export type DecisionContext =
  | { ok: true; request: DecisionRequest }
  | { ok: false; missing: string[] };

/**
 * Assembles the decision payload purely from what this browser session really
 * produced for the request (analysis contract, built plan, retrieval
 * responses). Returns which pieces are missing instead of inventing any.
 */
export function buildDecisionContext(requestId: string, userId?: string | number | null): DecisionContext {
  const missing: string[] = [];

  let agent1Output: Agent1OutputContract | null = null;
  try {
    const raw = sessionStorage.getItem(`analysis:${requestId}`);
    const parsed = raw ? (JSON.parse(raw) as FashionAnalysisResponse) : null;
    agent1Output = parsed?.raw_agent1_contract ?? null;
  } catch {
    agent1Output = null;
  }
  if (!agent1Output) missing.push('analysis result');

  const budgetResponse = readCachedPlan<BudgetOptimizationResponse>(requestId);
  if (!budgetResponse) missing.push('budget plan');

  const retrievalByCategory = readRetrievalContext<Record<string, RetrievalResponse>>(requestId);
  if (!retrievalByCategory) missing.push('retrieval results');

  if (missing.length > 0 || !agent1Output || !budgetResponse || !retrievalByCategory) {
    return { ok: false, missing };
  }

  return {
    ok: true,
    request: {
      request_id: requestId,
      agent1_output: agent1Output,
      budget_response: budgetResponse,
      retrieval_by_category: retrievalByCategory,
      user_id: userId ?? null,
    },
  };
}

export async function recommendOutfit(
  request: DecisionRequest,
  llmPolish = false
): Promise<DecisionResponse> {
  const { data } = await api.post<DecisionResponse>(
    `/decision/recommend${llmPolish ? '?llm_polish=true' : ''}`,
    request
  );
  return data;
}

export async function decisionHealth(): Promise<{ status: string; service: string }> {
  const { data } = await api.get('/decision/health');
  return data;
}
