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
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string, display_name: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

import { API_URL as API } from '../config';

const AuthContext = createContext<AuthContextType | null>(null);

const getToken = (): string | null => {
  try {
    const t = localStorage.getItem('token');
    if (t) return t;
    const f = sessionStorage.getItem('token');
    if (f) { localStorage.setItem('token', f); sessionStorage.removeItem('token'); return f; }
  } catch {}
  return null;
};

const getStoredUser = (): User | null => {
  try {
    const u = localStorage.getItem('user');
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
    fetch(`${API}/api/auth/me`, { headers: { Authorization: `Bearer ${t}` } })
      .then(r => r.ok ? r.json() : null)
      .then(u => {
        if (u) { setUser(u); localStorage.setItem('user', JSON.stringify(u)); }
        else { localStorage.removeItem('token'); localStorage.removeItem('user'); setToken(null); setUser(null); }
      })
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    const handler = () => {
      const t = getToken();
      if (!t) return;
      setToken(t);
    };
    window.addEventListener('auth-callback', handler);
    return () => window.removeEventListener('auth-callback', handler);
  }, []);

  const handleAuthResponse = useCallback((data: { access_token: string; user: User }) => {
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data.user));
    sessionStorage.removeItem('token');
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Login failed'); }
    handleAuthResponse(await res.json());
  }, [handleAuthResponse]);

  const signup = useCallback(async (email: string, password: string, display_name: string) => {
    const res = await fetch(`${API}/api/auth/signup`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, display_name })
    });
    if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Signup failed'); }
    handleAuthResponse(await res.json());
  }, [handleAuthResponse]);

  const logout = useCallback(() => {
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
