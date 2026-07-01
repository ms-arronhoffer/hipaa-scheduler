import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Spinner from "@cloudscape-design/components/spinner";
import ProtectedRoute from "./auth/ProtectedRoute";
import AppShell from "./components/layout/AppShell";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const MfaPage = lazy(() => import("./pages/MfaPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const PatientsPage = lazy(() => import("./pages/PatientsPage"));
const PatientDetailPage = lazy(() => import("./pages/PatientDetailPage"));
const AppointmentsPage = lazy(() => import("./pages/AppointmentsPage"));
const WaitlistPage = lazy(() => import("./pages/WaitlistPage"));
const OfficesPage = lazy(() => import("./pages/config/OfficesPage"));
const ProvidersPage = lazy(() => import("./pages/config/ProvidersPage"));
const AppointmentTypesPage = lazy(() => import("./pages/config/AppointmentTypesPage"));
const IntakeFormsPage = lazy(() => import("./pages/config/IntakeFormsPage"));
const IntakeFormBuilder = lazy(() => import("./pages/config/IntakeFormBuilder"));
const UsersPage = lazy(() => import("./pages/config/UsersPage"));
const ApiKeysPage = lazy(() => import("./pages/integrations/ApiKeysPage"));
const WebhooksPage = lazy(() => import("./pages/integrations/WebhooksPage"));
const CalendarConnectionsPage = lazy(() => import("./pages/integrations/CalendarConnectionsPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const ActivityLogPage = lazy(() => import("./pages/ActivityLogPage"));
const OrganizationPage = lazy(() => import("./pages/OrganizationPage"));
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
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/patients/:id" element={<PatientDetailPage />} />
            <Route path="/appointments" element={<AppointmentsPage />} />
            <Route path="/waitlist" element={<WaitlistPage />} />
            <Route path="/organization" element={<OrganizationPage />} />
            <Route path="/config/offices" element={<OfficesPage />} />
            <Route path="/config/providers" element={<ProvidersPage />} />
            <Route path="/config/appointment-types" element={<AppointmentTypesPage />} />
            <Route path="/config/users" element={<UsersPage />} />
            <Route path="/config/intake-forms" element={<IntakeFormsPage />} />
            <Route path="/config/intake-forms/:id" element={<IntakeFormBuilder />} />
            <Route path="/integrations/api-keys" element={<ApiKeysPage />} />
            <Route path="/integrations/webhooks" element={<WebhooksPage />} />
            <Route path="/integrations/calendar" element={<CalendarConnectionsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/activity-log" element={<ActivityLogPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>
      </Routes>
    </Suspense>
  );
}
