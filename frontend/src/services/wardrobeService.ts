import { api } from './api';
import type {
  ImageAnalysisDraft,
  WardrobeItem,
  WardrobeItemCreate,
} from '../types';

export interface WardrobeFilters {
  category?: string;
  colour?: string;
  style?: string;
  pattern?: string;
}

export async function listWardrobe(filters: WardrobeFilters = {}): Promise<WardrobeItem[]> {
  const { data } = await api.get<WardrobeItem[]>('/api/wardrobe', { params: filters });
  return data;
}

export async function getWardrobeItem(id: number): Promise<WardrobeItem> {
  const { data } = await api.get<WardrobeItem>(`/api/wardrobe/${id}`);
  return data;
}

export async function uploadAndAnalyze(file: File): Promise<ImageAnalysisDraft> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await api.post<ImageAnalysisDraft>('/api/wardrobe/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function createWardrobeItem(payload: WardrobeItemCreate): Promise<WardrobeItem> {
  const { data } = await api.post<WardrobeItem>('/api/wardrobe', payload);
  return data;
}

export async function updateWardrobeItem(
  id: number,
  payload: Partial<WardrobeItemCreate>
): Promise<WardrobeItem> {
  const { data } = await api.put<WardrobeItem>(`/api/wardrobe/${id}`, payload);
  return data;
}

export async function deleteWardrobeItem(id: number): Promise<void> {
  await api.delete(`/api/wardrobe/${id}`);
}
