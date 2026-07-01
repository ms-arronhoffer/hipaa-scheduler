import { Navigate, Outlet, useLocation } from "react-router-dom";
import Spinner from "@cloudscape-design/components/spinner";
import { useAuth } from "./AuthContext";

export default function ProtectedRoute() {
  const { isAuthenticated, loading, user } = useAuth();
  const location = useLocation();
  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "4rem" }}>
        <Spinner size="large" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (user && !user.is_super_admin && !user.impersonating) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
