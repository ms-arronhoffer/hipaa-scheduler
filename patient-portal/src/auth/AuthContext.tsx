import { createContext, ReactNode, useContext, useState, useCallback } from "react";
import { clearToken, getToken, setToken } from "../api/client";

interface AuthCtx {
  isAuthenticated: boolean;
  loginWithToken: (accessToken: string) => void;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(!!getToken());

  const loginWithToken = useCallback((accessToken: string) => {
    setToken(accessToken);
    setIsAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setIsAuthenticated(false);
  }, []);

  return (
    <Ctx.Provider value={{ isAuthenticated, loginWithToken, logout }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}
