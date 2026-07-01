import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Box from "@cloudscape-design/components/box";
import Spinner from "@cloudscape-design/components/spinner";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Toggle from "@cloudscape-design/components/toggle";
import Alert from "@cloudscape-design/components/alert";
import PageHeader from "../components/layout/PageHeader";
import { organizationApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

interface Organization {
  id: string;
  name: string;
  plan: string;
  seats: number;
  mfa_required: boolean;
  baa_signed_at: string | null;
  settings?: Record<string, unknown>;
}

export default function OrganizationPage() {
  const { push } = useFlash();
  const [org, setOrg] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    organizationApi.get()
      .then((r) => setOrg(r as Organization))
      .catch(() => push({ type: "error", content: "Failed to load organization" }))
      .finally(() => setLoading(false));
  }, [push]);

  async function save() {
    if (!org) return;
    setSaving(true);
    try {
      await organizationApi.update({ name: org.name, mfa_required: org.mfa_required });
      push({ type: "success", content: "Saved" });
    } catch {
      push({ type: "error", content: "Save failed" });
    } finally { setSaving(false); }
  }

  if (loading || !org) {
    return <PageHeader title="Organization"><Box textAlign="center" padding="xxl"><Spinner size="large" /></Box></PageHeader>;
  }

  return (
    <PageHeader title="Organization" description="Practice settings, plan, and HIPAA controls">
      <SpaceBetween size="l">
        {!org.baa_signed_at && (
          <Alert type="warning" header="BAA not on file">
            Your Business Associate Agreement has not been signed. Contact support to complete the BAA before storing PHI in production.
          </Alert>
        )}

        <Container header={<Header variant="h2">Plan</Header>}>
          <ColumnLayout columns={3} variant="text-grid">
            <div>
              <Box variant="awsui-key-label">Plan</Box>
              <div>{org.plan}</div>
            </div>
            <div>
              <Box variant="awsui-key-label">Seats</Box>
              <div>{org.seats}</div>
            </div>
            <div>
              <Box variant="awsui-key-label">BAA signed</Box>
              <div>{org.baa_signed_at ? new Date(org.baa_signed_at).toLocaleDateString() : "No"}</div>
            </div>
          </ColumnLayout>
        </Container>

        <Container header={<Header variant="h2" actions={<Button variant="primary" loading={saving} onClick={save}>Save</Button>}>Settings</Header>}>
          <Form>
            <SpaceBetween size="m">
              <FormField label="Practice name">
                <Input value={org.name} onChange={(e) => setOrg({ ...org, name: e.detail.value })} />
              </FormField>
              <FormField label="Require MFA for privileged roles" description="Practice admins, providers, and billing users must enroll TOTP">
                <Toggle checked={org.mfa_required} onChange={(e) => setOrg({ ...org, mfa_required: e.detail.checked })}>Required</Toggle>
              </FormField>
            </SpaceBetween>
          </Form>
        </Container>
      </SpaceBetween>
    </PageHeader>
  );
}
