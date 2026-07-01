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
  return (
    <div style={{ display: "flex", justifyContent: "center", padding: "4rem" }}>
      <Spinner size="large" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/mfa" element={<MfaPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/tenants" replace />} />
            <Route path="/tenants" element={<TenantsPage />} />
            <Route path="/tenants/:id" element={<TenantDetailPage />} />
            <Route path="/plans" element={<PlansPage />} />
            <Route path="/audit-search" element={<AuditSearchPage />} />
            <Route path="/baa" element={<BaaTrackingPage />} />
            <Route path="/health" element={<SystemHealthPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
