import { api } from './api';
import type {
  Agent1OutputContract,
  AgentStatus,
  FashionRequestInput,
  PresetAttack,
  SecurityThreatReport,
} from '../types';

export async function getAgentStatus(): Promise<AgentStatus> {
  const { data } = await api.get<AgentStatus>('/api/agent/status');
  return data;
}

export async function getAgentSchema(): Promise<Record<string, unknown>> {
  const { data } = await api.get<Record<string, unknown>>('/api/agent/schema');
  return data;
}

export async function agentAnalyze(
  payload: FashionRequestInput & { user_id?: number; request_id?: string }
): Promise<Agent1OutputContract> {
  const { data } = await api.post<Agent1OutputContract>('/api/agent/analyze', payload);
  return data;
}

export async function getHealth(): Promise<{ status: string; service: string; version: string }> {
  const { data } = await api.get('/api/health');
  return data;
}

export async function listSecurityPresets(): Promise<PresetAttack[]> {
  const { data } = await api.get<PresetAttack[]>('/api/security/presets');
  return data;
}

export async function testPromptInjection(test_prompt: string): Promise<SecurityThreatReport> {
  const { data } = await api.post<SecurityThreatReport>('/api/security/test-prompt', { test_prompt });
  return data;
}
