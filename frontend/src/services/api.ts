import axios from 'axios';
import type { ApiErrorBody } from '../types';

const TOKEN_KEY = 'fashora_token';

export const api = axios.create({
  baseURL: '',
  timeout: 60000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function extractErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (!axios.isAxiosError(err)) return fallback;
  const data = err.response?.data as ApiErrorBody | undefined;
  const detail = data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return detail.message || detail.code || fallback;
  }
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return err.message || fallback;
}

/** Normalize wardrobe image paths to a browser-fetchable URL. */
export function imageUrl(path?: string | null): string {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  if (path.startsWith('/')) return path;
  return `/${path}`;
}
