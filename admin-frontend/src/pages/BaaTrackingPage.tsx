import { FormEvent, useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import DatePicker from "@cloudscape-design/components/date-picker";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import { adminApi, BaaTenant } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.ceil(ms / 86400000);
}

function baaStatus(row: BaaTenant): React.JSX.Element {
  if (!row.baa_signed_at) return <StatusIndicator type="warning">Not signed</StatusIndicator>;
  const d = daysUntil(row.baa_expires_at);
  if (d === null) return <StatusIndicator type="success">Signed</StatusIndicator>;
  if (d < 0) return <StatusIndicator type="error">Expired</StatusIndicator>;
  if (d < 30) return <StatusIndicator type="warning">{`Expires in ${d}d`}</StatusIndicator>;
  return <StatusIndicator type="success">{`${d}d remaining`}</StatusIndicator>;
}

export default function BaaTrackingPage() {
  const { push } = useFlash();
  const [rows, setRows] = useState<BaaTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<BaaTenant | null>(null);
  const [signed, setSigned] = useState("");
  const [expires, setExpires] = useState("");
  const [docKey, setDocKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      setRows(await adminApi.listBaa());
    } catch {
      push({ type: "error", content: "Failed to load BAA tracking" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openEdit(row: BaaTenant) {
    setEditing(row);
    setSigned(row.baa_signed_at ? row.baa_signed_at.slice(0, 10) : "");
    setExpires(row.baa_expires_at ? row.baa_expires_at.slice(0, 10) : "");
    setDocKey(row.baa_document_key ?? "");
    setError(null);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      await adminApi.updateBaa(editing.org_id, {
        baa_signed_at: signed ? new Date(signed).toISOString() : null,
        baa_expires_at: expires ? new Date(expires).toISOString() : null,
        baa_document_key: docKey || null,
      });
      setEditing(null);
      push({ type: "success", content: "BAA record updated." });
      await reload();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail ?? (e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  const missing = rows.filter((r) => !r.baa_signed_at).length;

  return (
    <PageHeader
      title="BAA tracking"
      description="Business Associate Agreement status per tenant."
      actions={<Button iconName="refresh" onClick={reload} loading={loading} />}
    >
      <SpaceBetween size="l">
        {missing > 0 && (
          <Alert type="warning">
            {missing} tenant{missing === 1 ? "" : "s"} without a signed BAA. Do not
            let unsigned tenants process PHI.
          </Alert>
        )}
        <Table
          variant="container"
          loading={loading}
          loadingText="Loading BAA records"
          items={rows}
          columnDefinitions={[
            { id: "name", header: "Tenant", cell: (r) => r.org_name },
            { id: "status", header: "Status", cell: baaStatus },
            {
              id: "signed",
              header: "Signed",
              cell: (r) => (r.baa_signed_at ? new Date(r.baa_signed_at).toLocaleDateString() : "—"),
            },
            {
              id: "expires",
              header: "Expires",
              cell: (r) => (r.baa_expires_at ? new Date(r.baa_expires_at).toLocaleDateString() : "—"),
            },
            {
              id: "doc",
              header: "Document",
              cell: (r) => (r.baa_document_key ? <code>{r.baa_document_key}</code> : "—"),
            },
            { id: "contact", header: "Contact", cell: (r) => r.contact_email ?? "—" },
            {
              id: "actions",
              header: "",
              cell: (r) => (
                <Button variant="inline-link" onClick={() => openEdit(r)}>
                  Edit
                </Button>
              ),
            },
          ]}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No tenants yet</b>
            </Box>
          }
        />
      </SpaceBetween>

      <Modal
        visible={!!editing}
        onDismiss={() => setEditing(null)}
        header={editing ? `BAA — ${editing.org_name}` : ""}
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setEditing(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={saving}
                onClick={() => void save(new Event("submit") as unknown as FormEvent)}
              >
                Save
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <form onSubmit={save}>
          <Form>
            <SpaceBetween size="m">
              {error && <Alert type="error">{error}</Alert>}
              <FormField label="Signed on">
                <DatePicker value={signed} onChange={(e) => setSigned(e.detail.value)} />
              </FormField>
              <FormField label="Expires on">
                <DatePicker value={expires} onChange={(e) => setExpires(e.detail.value)} />
              </FormField>
              <FormField
                label="Document storage key"
                description="Object storage key for the signed PDF."
              >
                <Input value={docKey} onChange={(e) => setDocKey(e.detail.value)} />
              </FormField>
            </SpaceBetween>
          </Form>
        </form>
      </Modal>
    </PageHeader>
  );
}
