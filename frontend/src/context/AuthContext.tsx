import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';

interface User {
  email: string
  display_name: string
  auth_provider?: string
  email_verified?: boolean
  role?: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (email: string, password: string, remember?: boolean) => Promise<void>
  signup: (email: string, password: string, display_name: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

import { API_URL as API } from '../config';

const AuthContext = createContext<AuthContextType | null>(null);

const getToken = (): string | null => {
  try {
    const t = sessionStorage.getItem('token');
    if (t) return t;
    const remembered = localStorage.getItem('token');
    if (remembered) return remembered;
  } catch {}
  return null;
};

const getStoredUser = (): User | null => {
  try {
    const u = sessionStorage.getItem('user') || localStorage.getItem('user');
    return u ? JSON.parse(u) : null;
  } catch { return null; }
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [token, setToken] = useState<string | null>(getToken);
  const [user, setUser] = useState<User | null>(getStoredUser);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const t = getToken();
    if (!t) { setUser(null); setIsLoading(false); return; }
    fetch(`${API}/api/auth/me`, { credentials: 'include', headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.ok ? r.json() : null)
      .then(u => {
        if (u) { setUser(u); }
        else { localStorage.removeItem('token'); localStorage.removeItem('user'); sessionStorage.removeItem('token'); sessionStorage.removeItem('user'); setToken(null); setUser(null); }
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    const handler = () => {
      const t = getToken();
      if (!t) return;
      setToken(t);
      fetch(`${API}/api/auth/me`, { credentials: 'include', headers: { Authorization: `Bearer ${t}` } })
        .then(r => r.ok ? r.json() : null)
        .then(u => {
          if (u) { setUser(u); }
        })
        .catch(() => {});
    };
    window.addEventListener('auth-callback', handler);
    return () => window.removeEventListener('auth-callback', handler);
  }, []);

  const handleAuthResponse = useCallback((data: { access_token: string; user: User }, remember = false) => {
    (remember ? localStorage : sessionStorage).setItem('token', data.access_token);
    (remember ? localStorage : sessionStorage).setItem('user', JSON.stringify(data.user));
    if (!remember) localStorage.removeItem('token');
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const login = useCallback(async (email: string, password: string, remember = false) => {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Login failed'); }
    handleAuthResponse(await res.json(), remember);
  }, [handleAuthResponse]);

  const signup = useCallback(async (email: string, password: string, display_name: string) => {
    const res = await fetch(`${API}/api/auth/signup`, {
      method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, display_name })
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Signup failed'); }
    handleAuthResponse(await res.json());
  }, [handleAuthResponse]);

  const logout = useCallback(() => {
    fetch(`${API}/api/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    sessionStorage.removeItem('token');
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, token, login, signup, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};
