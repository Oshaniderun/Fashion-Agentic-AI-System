import { api, setStoredToken } from './api';
import type { AuthUser, TokenResponse, UserProfile } from '../types';

export async function register(name: string, email: string, password: string): Promise<AuthUser> {
  const { data } = await api.post<TokenResponse>('/api/auth/register', { name, email, password });
  setStoredToken(data.access_token);
  return { id: data.user_id, name: data.name, email: data.email, token: data.access_token };
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const { data } = await api.post<TokenResponse>('/api/auth/login', { email, password });
  setStoredToken(data.access_token);
  return { id: data.user_id, name: data.name, email: data.email, token: data.access_token };
}

export async function fetchMe(): Promise<UserProfile> {
  const { data } = await api.get<UserProfile>('/api/auth/me');
  return data;
}

export function logout() {
  setStoredToken(null);
}
