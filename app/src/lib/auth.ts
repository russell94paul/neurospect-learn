import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, TOKEN_KEY } from '@/lib/api';
import type { User, TokenResponse } from '@/types/api';

// ============================================================
// Context types
// ============================================================

interface AuthContextValue {
  token: string | null;
  user: User | null;
  isLoading: boolean;
  login: () => void;
  debugLogin: (discordId: string) => Promise<void>;
  logout: () => void;
  setToken: (token: string) => Promise<void>;
}

// ============================================================
// Context
// ============================================================

const AuthContext = createContext<AuthContextValue | null>(null);

// ============================================================
// Provider
// ============================================================

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY)
  );
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: validate existing token
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (!stored) {
      setIsLoading(false);
      return;
    }
    api
      .get('auth/me')
      .json<User>()
      .then((u) => {
        setUser(u);
        setTokenState(stored);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setTokenState(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  // Redirect to Discord OAuth
  const login = useCallback(() => {
    const clientId = import.meta.env.VITE_DISCORD_CLIENT_ID;
    const redirectUri = import.meta.env.VITE_DISCORD_REDIRECT_URI ?? 'http://localhost:5173/auth/callback';
    if (!clientId) {
      console.warn('VITE_DISCORD_CLIENT_ID not set');
      return;
    }
    const params = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: 'code',
      scope: 'identify',
    });
    window.location.href = `https://discord.com/api/oauth2/authorize?${params.toString()}`;
  }, []);

  // Debug login — POST /auth/debug/token {discord_id}
  const debugLogin = useCallback(async (discordId: string) => {
    const data = await api
      .post('auth/debug/token', { json: { discord_id: discordId } })
      .json<TokenResponse>();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setTokenState(data.access_token);
    const me = await api.get('auth/me').json<User>();
    setUser(me);
  }, []);

  // Logout — clear token + state
  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setTokenState(null);
    setUser(null);
    window.location.href = '/login';
  }, []);

  // setToken — called after OAuth callback
  const setToken = useCallback(async (newToken: string) => {
    localStorage.setItem(TOKEN_KEY, newToken);
    setTokenState(newToken);
    const me = await api.get('auth/me').json<User>();
    setUser(me);
  }, []);

  const value: AuthContextValue = {
    token,
    user,
    isLoading,
    login,
    debugLogin,
    logout,
    setToken,
  };

  return React.createElement(AuthContext.Provider, { value }, children);
}

// ============================================================
// Hook
// ============================================================

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
