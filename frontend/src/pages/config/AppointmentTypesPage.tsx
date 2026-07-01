import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Toggle from "@cloudscape-design/components/toggle";
import Form from "@cloudscape-design/components/form";
import PageHeader from "../../components/layout/PageHeader";
import { appointmentTypesApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface AppointmentType {
  id: string;
  name: string;
  duration_min: number;
  buffer_before_min: number;
  buffer_after_min: number;
  color?: string | null;
  active: boolean;
}

export default function AppointmentTypesPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<AppointmentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Partial<AppointmentType> | null>(null);
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    appointmentTypesApi.list()
      .then((r: unknown) => setItems(((r as { items?: AppointmentType[] }).items) ?? (r as AppointmentType[])))
      .catch(() => push({ type: "error", content: "Failed to load appointment types" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function submit() {
    if (!editing) return;
    setSaving(true);
    try {
      if (editing.id) await appointmentTypesApi.update(editing.id, editing);
      else await appointmentTypesApi.create(editing);
      push({ type: "success", content: "Saved" });
      setEditing(null);
      load();
    } catch {
      push({ type: "error", content: "Save failed" });
    } finally { setSaving(false); }
  }

  return (
    <PageHeader
      title="Appointment types"
      description="Define visit types, durations, and buffers"
      actions={<Button variant="primary" onClick={() => setEditing({ duration_min: 30, buffer_before_min: 0, buffer_after_min: 0, active: true })}>New type</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (t) => t.name },
          { id: "dur", header: "Duration (min)", cell: (t) => t.duration_min },
          { id: "before", header: "Buffer before", cell: (t) => t.buffer_before_min },
          { id: "after", header: "Buffer after", cell: (t) => t.buffer_after_min },
          { id: "active", header: "Active", cell: (t) => (t.active ? "Yes" : "No") },
          { id: "actions", header: "", cell: (t) => <Button variant="inline-link" onClick={() => setEditing(t)}>Edit</Button> },
        ]}
        header={<Header counter={`(${items.length})`}>Appointment types</Header>}
        empty={<Box textAlign="center" padding="l">No appointment types yet.</Box>}
      />

      <Modal
        visible={!!editing}
        onDismiss={() => setEditing(null)}
        header={editing?.id ? "Edit appointment type" : "New appointment type"}
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
              <FormField label="Duration (minutes)">
                <Input type="number" value={String(editing.duration_min ?? 30)} onChange={(e) => setEditing({ ...editing, duration_min: Number(e.detail.value) })} />
              </FormField>
              <FormField label="Buffer before (minutes)">
                <Input type="number" value={String(editing.buffer_before_min ?? 0)} onChange={(e) => setEditing({ ...editing, buffer_before_min: Number(e.detail.value) })} />
              </FormField>
              <FormField label="Buffer after (minutes)">
                <Input type="number" value={String(editing.buffer_after_min ?? 0)} onChange={(e) => setEditing({ ...editing, buffer_after_min: Number(e.detail.value) })} />
              </FormField>
              <Toggle checked={editing.active ?? true} onChange={(e) => setEditing({ ...editing, active: e.detail.checked })}>Active</Toggle>
            </SpaceBetween>
          </Form>
        )}
      </Modal>
    </PageHeader>
  );
}
