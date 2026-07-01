import { FormEvent, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Modal from "@cloudscape-design/components/modal";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Toggle from "@cloudscape-design/components/toggle";
import { adminApi, Plan, Tenant } from "../api/admin";
import { useAuth } from "../auth/AuthContext";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <div>{value}</div>
    </div>
  );
}

export default function TenantDetailPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const { push } = useFlash();
  const { beginImpersonation } = useAuth();
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);
  const [showPlanOverride, setShowPlanOverride] = useState(false);
  const [showSeatOverride, setShowSeatOverride] = useState(false);
  const [showImpersonate, setShowImpersonate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newPlan, setNewPlan] = useState<string>("");
  const [newSeats, setNewSeats] = useState<number>(0);
  const [reason, setReason] = useState("");

  async function reload() {
    setLoading(true);
    try {
      const [t, p] = await Promise.all([adminApi.getTenant(id), adminApi.listPlans()]);
      setTenant(t);
      setPlans(p);
      setNewPlan(t.plan);
      setNewSeats(t.seats);
    } catch {
      push({ type: "error", content: "Failed to load tenant" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function toggleMfa(mfa_required: boolean) {
    try {
      const t = await adminApi.updateTenant(id, { mfa_required });
      setTenant(t);
      push({ type: "success", content: "MFA policy updated." });
    } catch {
      push({ type: "error", content: "Failed to update MFA policy." });
    }
  }

  async function toggleActive() {
    if (!tenant) return;
    try {
      const t = tenant.active
        ? await adminApi.suspendTenant(id)
        : await adminApi.activateTenant(id);
      setTenant(t);
      push({
        type: "success",
        content: t.active ? "Tenant activated." : "Tenant suspended.",
      });
    } catch {
      push({ type: "error", content: "Failed to change tenant status." });
    }
  }

  async function submitPlanOverride(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const plan = plans.find((p) => p.name === newPlan);
      if (!plan) throw new Error("Unknown plan");
      const t = await adminApi.overridePlan(id, plan.id);
      setTenant(t);
      setShowPlanOverride(false);
      push({ type: "success", content: "Plan override applied." });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function submitSeatOverride(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const t = await adminApi.overrideSeats(id, newSeats);
      setTenant(t);
      setShowSeatOverride(false);
      push({ type: "success", content: `Seat cap set to ${t.seats}.` });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function submitImpersonate(e: FormEvent) {
    e.preventDefault();
    if (!reason.trim()) {
      setError("A reason is required for the audit log.");
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const res = await adminApi.impersonate(id, undefined, reason);
      await beginImpersonation(res.access_token);
      setShowImpersonate(false);
      push({
        type: "warning",
        content: "Impersonation session active. All actions are logged.",
      });
      window.location.href = "/";
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail ?? (e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (loading || !tenant) {
    return <PageHeader title="Tenant">Loading…</PageHeader>;
  }

  return (
    <PageHeader
      title={tenant.name}
      description={tenant.slug}
      actions={
        <SpaceBetween direction="horizontal" size="xs">
          <Button onClick={() => nav("/tenants")}>Back</Button>
          <Button onClick={reload} iconName="refresh" />
          <Button onClick={() => setShowImpersonate(true)} variant="normal">
            Impersonate
          </Button>
          <Button onClick={toggleActive} variant={tenant.active ? "normal" : "primary"}>
            {tenant.active ? "Suspend" : "Activate"}
          </Button>
        </SpaceBetween>
      }
    >
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Overview</Header>}>
          <ColumnLayout columns={3} variant="text-grid">
            <Field label="Plan" value={<code>{tenant.plan}</code>} />
            <Field label="Seats" value={`${tenant.seats_used} / ${tenant.seats}`} />
            <Field
              label="Status"
              value={
                tenant.active ? (
                  <StatusIndicator type="success">Active</StatusIndicator>
                ) : (
                  <StatusIndicator type="error">Suspended</StatusIndicator>
                )
              }
            />
            <Field
              label="BAA"
              value={
                tenant.baa_signed_at ? (
                  <StatusIndicator type="success">
                    Signed {new Date(tenant.baa_signed_at).toLocaleDateString()}
                  </StatusIndicator>
                ) : (
                  <StatusIndicator type="warning">Not signed</StatusIndicator>
                )
              }
            />
            <Field label="Created" value={new Date(tenant.created_at).toLocaleString()} />
            <Field label="Org ID" value={<code>{tenant.id}</code>} />
          </ColumnLayout>
        </Container>

        <Container
          header={
            <Header
              variant="h2"
              actions={
                <SpaceBetween direction="horizontal" size="xs">
                  <Button onClick={() => setShowPlanOverride(true)}>Override plan</Button>
                  <Button onClick={() => setShowSeatOverride(true)}>Override seats</Button>
                </SpaceBetween>
              }
            >
              Plan &amp; seats
            </Header>
          }
        >
          <Box variant="p">
            Overrides bypass the plan defaults for this tenant only. Use them for
            trial extensions or exception-based deals. The change is written to the
            cross-tenant audit log.
          </Box>
        </Container>

        <Container header={<Header variant="h2">Security</Header>}>
          <SpaceBetween size="m">
            <FormField
              label="Require MFA for privileged staff"
              description="Applies to practice_admin, provider, and billing roles."
            >
              <Toggle checked={tenant.mfa_required} onChange={(e) => void toggleMfa(e.detail.checked)}>
                {tenant.mfa_required ? "Required" : "Optional"}
              </Toggle>
            </FormField>
          </SpaceBetween>
        </Container>
      </SpaceBetween>

      <Modal
        visible={showPlanOverride}
        onDismiss={() => setShowPlanOverride(false)}
        header="Override plan"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowPlanOverride(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={saving}
                onClick={() => void submitPlanOverride(new Event("submit") as unknown as FormEvent)}
              >
                Apply
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <form onSubmit={submitPlanOverride}>
          <Form>
            <SpaceBetween size="m">
              {error && <Alert type="error">{error}</Alert>}
              <FormField label="Plan">
                <Select
                  selectedOption={{ value: newPlan, label: newPlan }}
                  options={plans.map((p) => ({ value: p.name, label: p.name }))}
                  onChange={(e) => setNewPlan(e.detail.selectedOption.value ?? "")}
                />
              </FormField>
            </SpaceBetween>
          </Form>
        </form>
      </Modal>

      <Modal
        visible={showSeatOverride}
        onDismiss={() => setShowSeatOverride(false)}
        header="Override seat cap"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowSeatOverride(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={saving}
                onClick={() => void submitSeatOverride(new Event("submit") as unknown as FormEvent)}
              >
                Apply
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <form onSubmit={submitSeatOverride}>
          <Form>
            <SpaceBetween size="m">
              {error && <Alert type="error">{error}</Alert>}
              <FormField label="Seats" description={`Currently using ${tenant.seats_used}.`}>
                <Input
                  type="number"
                  value={String(newSeats)}
                  onChange={(e) => setNewSeats(Number(e.detail.value) || 0)}
                />
              </FormField>
            </SpaceBetween>
          </Form>
        </form>
      </Modal>

      <Modal
        visible={showImpersonate}
        onDismiss={() => setShowImpersonate(false)}
        header="Impersonate tenant"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowImpersonate(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={saving}
                onClick={() => void submitImpersonate(new Event("submit") as unknown as FormEvent)}
              >
                Start impersonation
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <form onSubmit={submitImpersonate}>
          <Form>
            <SpaceBetween size="m">
              <Alert type="warning" statusIconAriaLabel="Warning">
                You are about to act as an administrator of{" "}
                <strong>{tenant.name}</strong>. All actions taken during the
                session are recorded to the audit log for this tenant and the
                super-admin log. Sessions expire after 15 minutes.
              </Alert>
              {error && <Alert type="error">{error}</Alert>}
              <FormField label="Reason" description="Required for the audit trail.">
                <Input value={reason} onChange={(e) => setReason(e.detail.value)} />
              </FormField>
            </SpaceBetween>
          </Form>
        </form>
      </Modal>
    </PageHeader>
  );
}
