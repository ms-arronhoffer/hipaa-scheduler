import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { clearTokens, getAdminToken, getImpersonationToken, setImpersonationToken, setRefreshToken, setToken, } from "../api/client";
const AuthContext = createContext(undefined);
export function AuthProvider({ children }) {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();
    const refresh = useCallback(async () => {
        if (!getAdminToken()) {
            setUser(null);
            setLoading(false);
            return;
        }
        try {
            const me = await authApi.me();
            setUser(me);
        }
        catch {
            setUser(null);
            clearTokens();
        }
        finally {
            setLoading(false);
        }
    }, []);
    useEffect(() => {
        void refresh();
    }, [refresh]);
    const login = useCallback(async (access, refreshTok) => {
        setToken(access);
        if (refreshTok)
            setRefreshToken(refreshTok);
        const me = await authApi.me();
        if (!me.is_super_admin) {
            clearTokens();
            setUser(null);
            throw new Error("Super-admin access required");
        }
        setUser(me);
    }, []);
    const logout = useCallback(async () => {
        try {
            await authApi.logout();
        }
        catch {
            /* best-effort */
        }
        clearTokens();
        setUser(null);
        navigate("/login", { replace: true });
    }, [navigate]);
    const beginImpersonation = useCallback(async (token) => {
        setImpersonationToken(token);
        const me = await authApi.me();
        setUser(me);
    }, []);
    const endImpersonation = useCallback(async () => {
        try {
            // Best-effort server-side revoke of the impersonation JWT.
            const { adminApi } = await import("../api/admin");
            await adminApi.endImpersonation();
        }
        catch {
            /* best-effort */
        }
        setImpersonationToken(null);
        const me = await authApi.me();
        setUser(me);
    }, []);
    const value = useMemo(() => ({
        user,
        loading,
        isAuthenticated: !!user,
        isImpersonating: !!getImpersonationToken(),
        login,
        logout,
        refresh,
        beginImpersonation,
        endImpersonation,
    }), [user, loading, login, logout, refresh, beginImpersonation, endImpersonation]);
    return _jsx(AuthContext.Provider, { value: value, children: children });
}
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx)
        throw new Error("useAuth must be used inside AuthProvider");
    return ctx;
}
