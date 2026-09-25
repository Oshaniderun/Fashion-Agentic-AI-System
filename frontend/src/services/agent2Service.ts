import { api } from './api';
import type {
  Agent2Product,
  Agent2Status,
  HandoffRetrievalResponse,
  RetrievalRequest,
  RetrievalResponse,
} from '../types/agent2';
import type { Agent2HandoffPayload } from '../types';

// All calls go through the shared axios instance (which attaches the user's
// JWT as Authorization: Bearer). Agent 2's require_auth accepts that JWT.
// The Vite dev proxy routes /api/v1 and /health to Agent 2 on port 8002.
// NOTE: the inter-agent service token is NEVER used or stored here — the
// browser authenticates only as the logged-in user.

export async function agent2Search(payload: RetrievalRequest): Promise<RetrievalResponse> {
  const { data } = await api.post<RetrievalResponse>('/api/v1/search', payload);
  return data;
}

export async function getAgent2Status(): Promise<Agent2Status> {
  const { data } = await api.get<Agent2Status>('/api/v1/status');
  return data;
}

export async function getAgent2Product(productId: string): Promise<Agent2Product> {
  const { data } = await api.get<Agent2Product>(`/api/v1/products/${encodeURIComponent(productId)}`);
  return data;
}

export async function agent2Health(): Promise<{ status: string; service: string; version: string }> {
  const { data } = await api.get('/health');
  return data;
}

export async function searchFromAgent1Handoff(
  payload: Agent2HandoffPayload
): Promise<HandoffRetrievalResponse> {
  const { data } = await api.post<HandoffRetrievalResponse>('/api/v1/search/agent1-handoff', payload);
  return data;
}
