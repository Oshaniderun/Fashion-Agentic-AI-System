import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import type { AuthUser } from '../types';
import * as authService from '../services/authService';
import { getStoredToken, setStoredToken } from '../services/api';

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const USER_KEY = 'fashora_user';

function loadCachedUser(): AuthUser | null {
  const token = getStoredToken();
  const raw = localStorage.getItem(USER_KEY);
  if (!token || !raw) return null;
  try {
    const parsed = JSON.parse(raw) as AuthUser;
    return { ...parsed, token };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const cached = loadCachedUser();
    if (!cached) {
      setLoading(false);
      return;
    }
    setUser(cached);
    authService
      .fetchMe()
      .then((profile) => {
        const next = {
          id: profile.id,
          name: profile.name,
          email: profile.email,
          token: cached.token,
        };
        setUser(next);
        localStorage.setItem(USER_KEY, JSON.stringify(next));
      })
      .catch(() => {
        setStoredToken(null);
        localStorage.removeItem(USER_KEY);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const next = await authService.login(email, password);
    setUser(next);
    localStorage.setItem(USER_KEY, JSON.stringify(next));
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const next = await authService.register(name, email, password);
    setUser(next);
    localStorage.setItem(USER_KEY, JSON.stringify(next));
  }, []);

  const logout = useCallback(() => {
    authService.logout();
    localStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
