import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Spinner from "@cloudscape-design/components/spinner";
import ProtectedRoute from "./auth/ProtectedRoute";
import AppShell from "./components/layout/AppShell";
const LoginPage = lazy(() => import("./pages/LoginPage"));
const MfaPage = lazy(() => import("./pages/MfaPage"));
const TenantsPage = lazy(() => import("./pages/TenantsPage"));
const TenantDetailPage = lazy(() => import("./pages/TenantDetailPage"));
const PlansPage = lazy(() => import("./pages/PlansPage"));
const AuditSearchPage = lazy(() => import("./pages/AuditSearchPage"));
const BaaTrackingPage = lazy(() => import("./pages/BaaTrackingPage"));
const SystemHealthPage = lazy(() => import("./pages/SystemHealthPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));
function Loading() {
    return (_jsx("div", { style: { display: "flex", justifyContent: "center", padding: "4rem" }, children: _jsx(Spinner, { size: "large" }) }));
}
export default function App() {
    return (_jsx(Suspense, { fallback: _jsx(Loading, {}), children: _jsxs(Routes, { children: [_jsx(Route, { path: "/login", element: _jsx(LoginPage, {}) }), _jsx(Route, { path: "/mfa", element: _jsx(MfaPage, {}) }), _jsx(Route, { element: _jsx(ProtectedRoute, {}), children: _jsxs(Route, { element: _jsx(AppShell, {}), children: [_jsx(Route, { path: "/", element: _jsx(Navigate, { to: "/tenants", replace: true }) }), _jsx(Route, { path: "/tenants", element: _jsx(TenantsPage, {}) }), _jsx(Route, { path: "/tenants/:id", element: _jsx(TenantDetailPage, {}) }), _jsx(Route, { path: "/plans", element: _jsx(PlansPage, {}) }), _jsx(Route, { path: "/audit-search", element: _jsx(AuditSearchPage, {}) }), _jsx(Route, { path: "/baa", element: _jsx(BaaTrackingPage, {}) }), _jsx(Route, { path: "/health", element: _jsx(SystemHealthPage, {}) }), _jsx(Route, { path: "*", element: _jsx(NotFoundPage, {}) })] }) })] }) }));
}
