import { jsx as _jsx } from "react/jsx-runtime";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import Spinner from "@cloudscape-design/components/spinner";
import { useAuth } from "./AuthContext";
export default function ProtectedRoute() {
    const { isAuthenticated, loading, user } = useAuth();
    const location = useLocation();
    if (loading) {
        return (_jsx("div", { style: { display: "flex", justifyContent: "center", padding: "4rem" }, children: _jsx(Spinner, { size: "large" }) }));
    }
    if (!isAuthenticated) {
        return _jsx(Navigate, { to: "/login", replace: true, state: { from: location.pathname } });
    }
    if (user && !user.is_super_admin && !user.impersonating) {
        return _jsx(Navigate, { to: "/login", replace: true });
    }
    return _jsx(Outlet, {});
}
