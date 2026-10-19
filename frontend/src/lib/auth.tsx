"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { auth as authAPI, tokens } from "@/lib/api";

export interface AuthUser {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  citizen_id?: string | null;
}

interface AuthState {
  user: AuthUser | null;
  /** true until the stored token (if any) has been checked against /auth/me */
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
  isAdmin: boolean;
}

const ADMIN_ROLES = ["state_admin", "system_admin"];
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access) { setLoading(false); return; }
    authAPI.me().then(setUser).catch(() => tokens.clear()).finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authAPI.login(email, password);
    tokens.set(res.access_token, res.refresh_token);
    setUser(res.user);
    return res.user as AuthUser;
  }, []);

  const register = useCallback(async (email: string, password: string, fullName: string) => {
    await authAPI.register(email, password, fullName);
    await login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try { await authAPI.logout(); } catch { /* token may already be invalid */ }
    tokens.clear();
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, register, logout, isAdmin: !!user && ADMIN_ROLES.includes(user.role) }),
    [user, loading, login, register, logout],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
