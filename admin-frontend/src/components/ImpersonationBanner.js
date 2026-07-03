import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import Alert from "@cloudscape-design/components/alert";
import Button from "@cloudscape-design/components/button";
import { useAuth } from "../auth/AuthContext";
// Persistent, high-visibility banner shown whenever a super-admin is acting as
// another tenant's user. Renders above all page chrome. The "Return" action
// revokes the impersonation JWT server-side and restores the admin session.
export function ImpersonationBanner() {
    const { isImpersonating, user, endImpersonation } = useAuth();
    if (!isImpersonating)
        return null;
    return (_jsx("div", { style: { position: "sticky", top: 0, zIndex: 1500 }, children: _jsx(Alert, { type: "warning", statusIconAriaLabel: "Impersonation active", children: _jsxs("div", { style: { display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }, children: [_jsxs("span", { children: [_jsx("strong", { children: "Impersonation active." }), " ", "Acting as ", _jsx("code", { children: user?.email ?? "unknown" }), user?.impersonated_org_id ? (_jsxs(_Fragment, { children: [" ", "in org ", _jsx("code", { children: user.impersonated_org_id })] })) : null, ". Every action is written to the audit log."] }), _jsx(Button, { variant: "primary", onClick: () => {
                            void endImpersonation();
                        }, children: "Return to admin" })] }) }) }));
}
