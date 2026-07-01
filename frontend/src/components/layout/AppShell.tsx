import { Outlet, useLocation, useNavigate } from "react-router-dom";
import AppLayout from "@cloudscape-design/components/app-layout";
import SideNavigation, { SideNavigationProps } from "@cloudscape-design/components/side-navigation";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useAuth } from "../../auth/AuthContext";

const NAV_ITEMS: SideNavigationProps.Item[] = [
  { type: "link", text: "Dashboard", href: "/dashboard" },
  { type: "link", text: "Calendar", href: "/calendar" },
  { type: "link", text: "Patients", href: "/patients" },
  { type: "link", text: "Appointments", href: "/appointments" },
  { type: "link", text: "Waitlist", href: "/waitlist" },
  { type: "divider" },
  {
    type: "section",
    text: "Configuration",
    items: [
      { type: "link", text: "Offices", href: "/config/offices" },
      { type: "link", text: "Providers", href: "/config/providers" },
      { type: "link", text: "Appointment types", href: "/config/appointment-types" },
      { type: "link", text: "Staff users", href: "/config/users" },
      { type: "link", text: "Intake forms", href: "/config/intake-forms" },
    ],
  },
  {
    type: "section",
    text: "Integrations",
    items: [
      { type: "link", text: "API keys", href: "/integrations/api-keys" },
      { type: "link", text: "Webhooks", href: "/integrations/webhooks" },
      { type: "link", text: "Calendar sync", href: "/integrations/calendar" },
    ],
  },
  { type: "divider" },
  { type: "link", text: "Reports", href: "/reports" },
  { type: "link", text: "PHI access log", href: "/activity-log" },
  { type: "link", text: "Organization", href: "/organization" },
];

export default function AppShell() {
  const nav = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const initials = user
    ? `${user.first_name?.[0] ?? user.email[0]}`.toUpperCase()
    : "";

  return (
    <>
      <div id="h" style={{ position: "sticky", top: 0, zIndex: 1002 }}>
        <TopNavigation
          identity={{
            href: "/",
            title: "HIPAA Scheduler",
            onFollow: (e) => {
              e.preventDefault();
              nav("/dashboard");
            },
          }}
          utilities={[
            {
              type: "menu-dropdown",
              text: user?.email ?? "",
              description: user?.roles.join(", "),
              iconName: "user-profile",
              ariaLabel: `Signed in as ${user?.email ?? ""}`,
              items: [
                { id: "profile", text: initials ? `Signed in: ${user?.email}` : "Profile", disabled: true },
                { id: "signout", text: "Sign out" },
              ],
              onItemClick: (e) => {
                if (e.detail.id === "signout") void logout();
              },
            },
          ]}
        />
      </div>
      <AppLayout
        headerSelector="#h"
        toolsHide
        navigation={
          <SideNavigation
            header={{ text: "Scheduler", href: "/dashboard" }}
            activeHref={location.pathname}
            items={NAV_ITEMS}
            onFollow={(e) => {
              if (!e.detail.external) {
                e.preventDefault();
                nav(e.detail.href);
              }
            }}
          />
        }
        content={<Outlet />}
        contentType="default"
      />
    </>
  );
}
