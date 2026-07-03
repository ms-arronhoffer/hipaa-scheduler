import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import AppLayout from "@cloudscape-design/components/app-layout";
import SideNavigation from "@cloudscape-design/components/side-navigation";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useAuth } from "../../auth/AuthContext";
const NAV_ITEMS = [
    { type: "link", text: "Tenants", href: "/tenants" },
    { type: "link", text: "Plans", href: "/plans" },
    { type: "link", text: "Audit search", href: "/audit-search" },
    { type: "link", text: "BAA tracking", href: "/baa" },
    { type: "link", text: "System health", href: "/health" },
];
export default function AppShell() {
    const nav = useNavigate();
    const location = useLocation();
    const { user, logout } = useAuth();
    return (_jsxs(_Fragment, { children: [_jsx("div", { id: "h", style: { position: "sticky", top: 0, zIndex: 1002 }, children: _jsx(TopNavigation, { identity: {
                        href: "/",
                        title: "HIPAA Scheduler — Admin",
                        onFollow: (e) => {
                            e.preventDefault();
                            nav("/tenants");
                        },
                    }, utilities: [
                        {
                            type: "menu-dropdown",
                            text: user?.email ?? "",
                            description: "super-admin",
                            iconName: "user-profile",
                            ariaLabel: `Signed in as ${user?.email ?? ""}`,
                            items: [{ id: "signout", text: "Sign out" }],
                            onItemClick: (e) => {
                                if (e.detail.id === "signout")
                                    void logout();
                            },
                        },
                    ] }) }), _jsx(AppLayout, { headerSelector: "#h", toolsHide: true, navigation: _jsx(SideNavigation, { header: { text: "Admin", href: "/tenants" }, activeHref: location.pathname, items: NAV_ITEMS, onFollow: (e) => {
                        if (!e.detail.external) {
                            e.preventDefault();
                            nav(e.detail.href);
                        }
                    } }), content: _jsx(Outlet, {}), contentType: "default" })] }));
}
