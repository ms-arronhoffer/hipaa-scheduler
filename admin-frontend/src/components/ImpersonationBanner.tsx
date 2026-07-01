import Alert from "@cloudscape-design/components/alert";
import Button from "@cloudscape-design/components/button";
import { useAuth } from "../auth/AuthContext";

// Persistent, high-visibility banner shown whenever a super-admin is acting as
// another tenant's user. Renders above all page chrome. The "Return" action
// revokes the impersonation JWT server-side and restores the admin session.
export function ImpersonationBanner() {
  const { isImpersonating, user, endImpersonation } = useAuth();
  if (!isImpersonating) return null;

  return (
    <div style={{ position: "sticky", top: 0, zIndex: 1500 }}>
      <Alert type="warning" statusIconAriaLabel="Impersonation active">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
          <span>
            <strong>Impersonation active.</strong>{" "}
            Acting as <code>{user?.email ?? "unknown"}</code>
            {user?.impersonated_org_id ? (
              <>
                {" "}
                in org <code>{user.impersonated_org_id}</code>
              </>
            ) : null}
            . Every action is written to the audit log.
          </span>
          <Button
            variant="primary"
            onClick={() => {
              void endImpersonation();
            }}
          >
            Return to admin
          </Button>
        </div>
      </Alert>
    </div>
  );
}
