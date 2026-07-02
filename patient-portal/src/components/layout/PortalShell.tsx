import { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useAuth } from "../../auth/AuthContext";

export default function PortalShell({ children }: { children: ReactNode }) {
  const nav = useNavigate();
  const { isAuthenticated, logout } = useAuth();

  return (
    <>
      <TopNavigation
        identity={{
          href: "/",
          title: "Book an appointment",
        }}
        utilities={
          isAuthenticated
            ? [
                {
                  type: "button",
                  text: "My appointments",
                  onClick: () => nav("/me/appointments"),
                },
                {
                  type: "button",
                  text: "Consents & documents",
                  onClick: () => nav("/me/consents"),
                },
                {
                  type: "button",
                  text: "Intake forms",
                  onClick: () => nav("/me/intake"),
                },
                {
                  type: "button",
                  text: "Security",
                  onClick: () => nav("/me/security"),
                },
                {
                  type: "button",
                  text: "Sign out",
                  onClick: () => {
                    logout();
                    nav("/login");
                  },
                },
              ]
            : [
                {
                  type: "button",
                  text: "Sign in",
                  onClick: () => nav("/login"),
                },
              ]
        }
      />
      <main style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>{children}</main>
    </>
  );
}
