import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { api, getToken, setToken } from "@/lib/api";

export interface Me {
  id: number;
  email: string;
  name: string | null;
  roles: string[];
  permissions: string[];
  is_admin: boolean;
  has_access: boolean;
}

interface AuthContextValue {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string, mfaCode?: string) => Promise<void>;
  logout: () => void;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setMe(null);
      setLoading(false);
      return;
    }
    try {
      setMe(await api.get<Me>("/api/v1/auth/me"));
    } catch {
      setToken(null);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  const login = useCallback(
    async (email: string, password: string, mfaCode?: string) => {
      const token = await api.login(email, password, mfaCode);
      setToken(token);
      setLoading(true);
      await loadMe();
    },
    [loadMe]
  );

  const logout = useCallback(() => {
    setToken(null);
    setMe(null);
  }, []);

  const can = useCallback(
    (permission: string) =>
      !!me && (me.roles.includes("admin") || me.permissions.includes(permission)),
    [me]
  );

  const value = useMemo(
    () => ({ me, loading, login, logout, can }),
    [me, loading, login, logout, can]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
