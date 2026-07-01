import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import Box from "@cloudscape-design/components/box";
import Spinner from "@cloudscape-design/components/spinner";
import PortalShell from "./components/layout/PortalShell";
import ProtectedRoute from "./auth/ProtectedRoute";

const OrgLandingPage = lazy(() => import("./pages/OrgLandingPage"));
const BookFlowPage = lazy(() => import("./pages/BookFlowPage"));
const GuestBookPage = lazy(() => import("./pages/GuestBookPage"));
const BookedPage = lazy(() => import("./pages/BookedPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const MagicConsumePage = lazy(() => import("./pages/MagicConsumePage"));
const ClaimPage = lazy(() => import("./pages/ClaimPage"));
const MyAppointmentsPage = lazy(() => import("./pages/MyAppointmentsPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));

function Loader() {
  return (
    <Box textAlign="center" padding="xxl">
      <Spinner size="large" />
    </Box>
  );
}

export default function App() {
  return (
    <Suspense fallback={<Loader />}>
      <PortalShell>
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />

          <Route path="/o/:slug" element={<OrgLandingPage />} />
          <Route path="/o/:slug/book" element={<BookFlowPage />} />
          <Route path="/o/:slug/book/guest" element={<GuestBookPage />} />
          <Route path="/o/:slug/booked" element={<BookedPage />} />

          <Route path="/login" element={<LoginPage />} />
          <Route path="/magic/:token" element={<MagicConsumePage />} />
          <Route path="/claim/:token" element={<ClaimPage />} />

          <Route
            path="/me/appointments"
            element={
              <ProtectedRoute>
                <MyAppointmentsPage />
              </ProtectedRoute>
            }
          />

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </PortalShell>
    </Suspense>
  );
}
