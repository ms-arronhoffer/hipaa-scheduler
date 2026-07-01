import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import Input from "@cloudscape-design/components/input";
import FormField from "@cloudscape-design/components/form-field";
import Form from "@cloudscape-design/components/form";
import PageHeader from "../../components/layout/PageHeader";
import { intakeFormsApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface IntakeForm {
  id: string;
  name: string;
  version: number;
  updated_at: string;
  active: boolean;
}

export default function IntakeFormsPage() {
  const { push } = useFlash();
  const nav = useNavigate();
  const [items, setItems] = useState<IntakeForm[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    intakeFormsApi.list()
      .then((r: unknown) => setItems(((r as { items?: IntakeForm[] }).items) ?? (r as IntakeForm[])))
      .catch(() => push({ type: "error", content: "Failed to load forms" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function create() {
    setSaving(true);
    try {
      const f = await intakeFormsApi.create({
        name,
        definition: { version: 1, pages: [{ sections: [{ fields: [] }] }] },
      }) as IntakeForm;
      push({ type: "success", content: "Form created" });
      setCreating(false);
      setName("");
      nav(`/config/intake-forms/${f.id}`);
    } catch {
      push({ type: "error", content: "Create failed" });
    } finally { setSaving(false); }
  }

  return (
    <PageHeader
      title="Intake forms"
      description="Design and version patient intake forms"
      actions={<Button variant="primary" onClick={() => setCreating(true)}>New form</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (f) => f.name },
          { id: "version", header: "Version", cell: (f) => f.version },
          { id: "updated", header: "Last updated", cell: (f) => new Date(f.updated_at).toLocaleString() },
          { id: "active", header: "Active", cell: (f) => (f.active ? "Yes" : "No") },
          { id: "actions", header: "", cell: (f) => <Button variant="inline-link" onClick={() => nav(`/config/intake-forms/${f.id}`)}>Edit</Button> },
        ]}
        header={<Header counter={`(${items.length})`}>Intake forms</Header>}
        empty={<Box textAlign="center" padding="l">No forms yet.</Box>}
      />

      <Modal
        visible={creating}
        onDismiss={() => setCreating(false)}
        header="New intake form"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setCreating(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={create} disabled={!name}>Create</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Form>
          <FormField label="Form name">
            <Input value={name} onChange={(e) => setName(e.detail.value)} placeholder="New patient intake" />
          </FormField>
        </Form>
      </Modal>
    </PageHeader>
  );
}
