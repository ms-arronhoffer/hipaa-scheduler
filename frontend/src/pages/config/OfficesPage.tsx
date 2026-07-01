import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Form from "@cloudscape-design/components/form";
import PageHeader from "../../components/layout/PageHeader";
import { officesApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface Office {
  id: string;
  name: string;
  timezone: string;
  address?: string | null;
  phone?: string | null;
}

export default function OfficesPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<Office[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Partial<Office> | null>(null);
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    officesApi.list()
      .then((r: unknown) => setItems(((r as { items?: Office[] }).items) ?? (r as Office[])))
      .catch(() => push({ type: "error", content: "Failed to load offices" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function submit() {
    if (!editing) return;
    setSaving(true);
    try {
      if (editing.id) await officesApi.update(editing.id, editing);
      else await officesApi.create(editing);
      push({ type: "success", content: "Saved" });
      setEditing(null);
      load();
    } catch {
      push({ type: "error", content: "Save failed" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageHeader
      title="Offices"
      description="Locations where appointments are scheduled"
      actions={<Button variant="primary" onClick={() => setEditing({ timezone: "America/New_York" })}>New office</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (o) => o.name },
          { id: "tz", header: "Timezone", cell: (o) => o.timezone },
          { id: "address", header: "Address", cell: (o) => o.address ?? "—" },
          { id: "phone", header: "Phone", cell: (o) => o.phone ?? "—" },
          { id: "actions", header: "", cell: (o) => <Button variant="inline-link" onClick={() => setEditing(o)}>Edit</Button> },
        ]}
        header={<Header counter={`(${items.length})`}>Offices</Header>}
        empty={<Box textAlign="center" padding="l">No offices yet.</Box>}
      />

      <Modal
        visible={!!editing}
        onDismiss={() => setEditing(null)}
        header={editing?.id ? "Edit office" : "New office"}
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setEditing(null)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={submit}>Save</Button>
            </SpaceBetween>
          </Box>
        }
      >
        {editing && (
          <Form>
            <SpaceBetween size="m">
              <FormField label="Name">
                <Input value={editing.name ?? ""} onChange={(e) => setEditing({ ...editing, name: e.detail.value })} />
              </FormField>
              <FormField label="Timezone" description="IANA timezone (e.g., America/New_York)">
                <Input value={editing.timezone ?? ""} onChange={(e) => setEditing({ ...editing, timezone: e.detail.value })} />
              </FormField>
              <FormField label="Address">
                <Input value={editing.address ?? ""} onChange={(e) => setEditing({ ...editing, address: e.detail.value })} />
              </FormField>
              <FormField label="Phone">
                <Input value={editing.phone ?? ""} onChange={(e) => setEditing({ ...editing, phone: e.detail.value })} />
              </FormField>
            </SpaceBetween>
          </Form>
        )}
      </Modal>
    </PageHeader>
  );
}
