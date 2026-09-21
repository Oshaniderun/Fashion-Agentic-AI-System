import { api } from './api';
import type { FashionAnalysisResponse, FashionRequestInput } from '../types';

export async function analyzeRequest(payload: FashionRequestInput): Promise<FashionAnalysisResponse> {
  const { data } = await api.post<FashionAnalysisResponse>('/api/analyze/request', payload);
  return data;
}

export async function getAnalysis(requestId: string): Promise<FashionAnalysisResponse> {
  const { data } = await api.get<FashionAnalysisResponse>(`/api/analyze/${requestId}`);
  return data;
}

export async function getLatestAnalysis(): Promise<FashionAnalysisResponse | null> {
  const { data } = await api.get<FashionAnalysisResponse | null>('/api/analyze/recent/latest');
  return data;
}
