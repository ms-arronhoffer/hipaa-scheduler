import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Alert from "@cloudscape-design/components/alert";
import Multiselect, { MultiselectProps } from "@cloudscape-design/components/multiselect";
import PageHeader from "../../components/layout/PageHeader";
import { apiKeysApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  last_used_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
}

const SCOPE_OPTIONS: MultiselectProps.Option[] = [
  { label: "Read patients", value: "patients:read" },
  { label: "Write patients", value: "patients:write" },
  { label: "Read appointments", value: "appointments:read" },
  { label: "Write appointments", value: "appointments:write" },
  { label: "Read availability", value: "availability:read" },
  { label: "Send notifications", value: "notifications:send" },
];

export default function ApiKeysPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [scopes, setScopes] = useState<MultiselectProps.Option[]>([]);
  const [saving, setSaving] = useState(false);
  const [plaintext, setPlaintext] = useState<string | null>(null);

  function load() {
    setLoading(true);
    apiKeysApi.list()
      .then((r: unknown) => setItems(((r as { items?: ApiKey[] }).items) ?? (r as ApiKey[])))
      .catch(() => push({ type: "error", content: "Failed to load API keys" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function create() {
    setSaving(true);
    try {
      const res = await apiKeysApi.create({ name, scopes: scopes.map((s) => s.value!) });
      setPlaintext(res.plaintext);
      setCreating(false);
      setName("");
      setScopes([]);
      load();
    } catch {
      push({ type: "error", content: "Create failed" });
    } finally { setSaving(false); }
  }

  async function revoke(k: ApiKey) {
    if (!confirm(`Revoke ${k.prefix}...? Applications using this key will start receiving 401 errors.`)) return;
    try {
      await apiKeysApi.revoke(k.id);
      push({ type: "success", content: "Key revoked" });
      load();
    } catch {
      push({ type: "error", content: "Revoke failed" });
    }
  }

  return (
    <PageHeader
      title="API keys"
      description="Programmatic access to the scheduling API. Keys are prefixed with hs_ and shown only once at creation."
      actions={<Button variant="primary" onClick={() => setCreating(true)}>New key</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (k) => k.name },
          { id: "prefix", header: "Prefix", cell: (k) => k.prefix + "…" },
          { id: "scopes", header: "Scopes", cell: (k) => k.scopes.join(", ") },
          { id: "last", header: "Last used", cell: (k) => k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "Never" },
          { id: "status", header: "Status", cell: (k) => k.revoked_at ? "Revoked" : "Active" },
          { id: "actions", header: "", cell: (k) => !k.revoked_at && <Button variant="inline-link" onClick={() => revoke(k)}>Revoke</Button> },
        ]}
        header={<Header counter={`(${items.length})`}>API keys</Header>}
        empty={<Box textAlign="center" padding="l">No API keys yet.</Box>}
      />

      <Modal
        visible={creating}
        onDismiss={() => setCreating(false)}
        header="New API key"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setCreating(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={create} disabled={!name || scopes.length === 0}>Create</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <FormField label="Name" description="Where will this key be used?">
            <Input value={name} onChange={(e) => setName(e.detail.value)} />
          </FormField>
          <FormField label="Scopes">
            <Multiselect selectedOptions={scopes} options={SCOPE_OPTIONS} onChange={({ detail }) => setScopes([...detail.selectedOptions])} />
          </FormField>
        </SpaceBetween>
      </Modal>

      <Modal
        visible={!!plaintext}
        onDismiss={() => setPlaintext(null)}
        header="API key created"
        footer={
          <Box float="right">
            <Button variant="primary" onClick={() => setPlaintext(null)}>I've saved it</Button>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Alert type="warning" header="Copy this key now">
            This key will never be shown again. Store it in your secrets manager before closing this dialog.
          </Alert>
          <Box variant="code" padding="s">
            <div style={{ wordBreak: "break-all", fontFamily: "monospace" }}>{plaintext}</div>
          </Box>
        </SpaceBetween>
      </Modal>
    </PageHeader>
  );
}
