import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi, CurrentUser } from "../api/auth";
import { clearTokens, getToken, setRefreshToken, setToken } from "../api/client";

type AuthState = {
  user: CurrentUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (access: string, refresh?: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await authApi.me();
      setUser(me);
    } catch {
      setUser(null);
      clearTokens();
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const login = useCallback(
    async (access: string, refreshTok?: string) => {
      setToken(access);
      if (refreshTok) setRefreshToken(refreshTok);
      const me = await authApi.me();
      setUser(me);
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      /* best-effort */
    }
    clearTokens();
    setUser(null);
    navigate("/login", { replace: true });
  }, [navigate]);

  const value = useMemo<AuthState>(
    () => ({ user, loading, isAuthenticated: !!user, login, logout, refresh }),
    [user, loading, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
