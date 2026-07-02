import { useEffect, useState } from "react";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { useNavigate } from "react-router-dom";
import { portalApi, PortalSession } from "../api/portal";
import { useAuth } from "../auth/AuthContext";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

function ValueField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <div>{children}</div>
    </div>
  );
}

export default function SecurityPage() {
  const { push } = useFlash();
  const { logout } = useAuth();
  const nav = useNavigate();
  const [session, setSession] = useState<PortalSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState(false);
  const [working, setWorking] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      setSession(await portalApi.session());
    } catch {
      push({ type: "error", content: "Could not load session details." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function signOutEverywhere() {
    setWorking(true);
    try {
      await portalApi.signOutEverywhere();
      // The current token was issued before the new cutoff, so it is now
      // revoked too — clear it locally and return to the sign-in page.
      setConfirm(false);
      logout();
      push({ type: "success", content: "Signed out of all devices." });
      nav("/login");
    } catch {
      push({ type: "error", content: "Could not sign out of all devices." });
    } finally {
      setWorking(false);
    }
  }

  const fmt = (v: string | null) => (v ? new Date(v).toLocaleString() : "—");

  return (
    <PageHeader
      title="Security & sessions"
      description="Review your account security and manage signed-in devices."
      actions={<Button iconName="refresh" onClick={reload} loading={loading} />}
    >
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Account</Header>}>
          <ColumnLayout columns={2} variant="text-grid">
            <ValueField label="Email">{session?.email ?? "—"}</ValueField>
            <ValueField label="Sign-in method">{session?.auth_mode ?? "—"}</ValueField>
            <ValueField label="Multi-factor authentication">
              {session?.mfa_enrolled ? (
                <StatusIndicator type="success">Enabled</StatusIndicator>
              ) : (
                <StatusIndicator type="warning">Not enabled</StatusIndicator>
              )}
            </ValueField>
            <ValueField label="Last sign-in">{fmt(session?.last_login_at ?? null)}</ValueField>
          </ColumnLayout>
        </Container>

        <Container header={<Header variant="h2">This session</Header>}>
          <ColumnLayout columns={2} variant="text-grid">
            <ValueField label="Signed in at">
              {fmt(session?.current_session_issued_at ?? null)}
            </ValueField>
            <ValueField label="Sessions revoked before">
              {fmt(session?.sessions_invalid_after ?? null)}
            </ValueField>
          </ColumnLayout>
        </Container>

        <Container
          header={
            <Header
              variant="h2"
              description="Sign out of every device, including this one. You'll need to sign in again."
            >
              Devices
            </Header>
          }
        >
          <Button onClick={() => setConfirm(true)}>Sign out everywhere</Button>
        </Container>
      </SpaceBetween>

      <Modal
        visible={confirm}
        onDismiss={() => setConfirm(false)}
        header="Sign out of all devices?"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setConfirm(false)} disabled={working}>
                Keep me signed in
              </Button>
              <Button variant="primary" loading={working} onClick={signOutEverywhere}>
                Sign out everywhere
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        This immediately revokes every active session, including the one on this device.
        You will be returned to the sign-in page.
      </Modal>
    </PageHeader>
  );
}
