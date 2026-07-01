import { ReactNode } from "react";
import { useAuth } from "./AuthContext";

// Hide UI elements the current user's roles don't permit. Server still
// enforces authorization — this only removes obvious dead-ends from the UI.
export function RoleGuard({
  roles,
  children,
  fallback = null,
}: {
  roles: string[];
  children: ReactNode;
  fallback?: ReactNode;
}) {
  const { user } = useAuth();
  if (!user) return fallback;
  if (user.is_super_admin) return <>{children}</>;
  if (user.roles.some((r) => roles.includes(r))) return <>{children}</>;
  return <>{fallback}</>;
}
