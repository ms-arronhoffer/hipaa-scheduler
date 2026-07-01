import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Multiselect, { MultiselectProps } from "@cloudscape-design/components/multiselect";
import Form from "@cloudscape-design/components/form";
import PageHeader from "../../components/layout/PageHeader";
import { usersApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface StaffUser {
  id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  roles: string[];
  mfa_enrolled: boolean;
  locked_until?: string | null;
}

const ROLE_OPTIONS: MultiselectProps.Option[] = [
  { label: "Practice admin", value: "practice_admin" },
  { label: "Provider", value: "provider" },
  { label: "Front desk", value: "front_desk" },
  { label: "Billing", value: "billing" },
];

export default function UsersPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<StaffUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Partial<StaffUser> | null>(null);
  const [saving, setSaving] = useState(false);

  function load() {
    setLoading(true);
    usersApi.list()
      .then((r: unknown) => setItems(((r as { items?: StaffUser[] }).items) ?? (r as StaffUser[])))
      .catch(() => push({ type: "error", content: "Failed to load users" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function submit() {
    if (!editing) return;
    setSaving(true);
    try {
      if (editing.id) await usersApi.update(editing.id, editing);
      else await usersApi.create(editing);
      push({ type: "success", content: "Saved" });
      setEditing(null);
      load();
    } catch {
      push({ type: "error", content: "Save failed" });
    } finally { setSaving(false); }
  }

  const selectedRoles = (editing?.roles ?? []).map((r) => ROLE_OPTIONS.find((o) => o.value === r) ?? { label: r, value: r });

  return (
    <PageHeader
      title="Staff users"
      description="Practice admins, providers, front-desk, and billing"
      actions={<Button variant="primary" onClick={() => setEditing({ roles: ["front_desk"] })}>New user</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "email", header: "Email", cell: (u) => u.email },
          { id: "name", header: "Name", cell: (u) => `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim() || "—" },
          { id: "roles", header: "Roles", cell: (u) => u.roles.join(", ") },
          { id: "mfa", header: "MFA", cell: (u) => (u.mfa_enrolled ? "Enrolled" : "Not enrolled") },
          { id: "locked", header: "Locked", cell: (u) => (u.locked_until && new Date(u.locked_until) > new Date() ? "Yes" : "No") },
          { id: "actions", header: "", cell: (u) => <Button variant="inline-link" onClick={() => setEditing(u)}>Edit</Button> },
        ]}
        header={<Header counter={`(${items.length})`}>Staff users</Header>}
        empty={<Box textAlign="center" padding="l">No staff users yet.</Box>}
      />

      <Modal
        visible={!!editing}
        onDismiss={() => setEditing(null)}
        header={editing?.id ? "Edit staff user" : "New staff user"}
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
              <FormField label="Email">
                <Input type="email" value={editing.email ?? ""} onChange={(e) => setEditing({ ...editing, email: e.detail.value })} />
              </FormField>
              <FormField label="First name">
                <Input value={editing.first_name ?? ""} onChange={(e) => setEditing({ ...editing, first_name: e.detail.value })} />
              </FormField>
              <FormField label="Last name">
                <Input value={editing.last_name ?? ""} onChange={(e) => setEditing({ ...editing, last_name: e.detail.value })} />
              </FormField>
              <FormField label="Roles">
                <Multiselect
                  selectedOptions={selectedRoles}
                  options={ROLE_OPTIONS}
                  onChange={({ detail }) => setEditing({ ...editing, roles: detail.selectedOptions.map((o) => o.value!) })}
                />
              </FormField>
              {!editing.id && (
                <FormField label="Temporary password" description="User will be prompted to enroll MFA on first login">
                  <Input type="password" value={(editing as { password?: string }).password ?? ""} onChange={(e) => setEditing({ ...editing, password: e.detail.value } as Partial<StaffUser>)} />
                </FormField>
              )}
            </SpaceBetween>
          </Form>
        )}
      </Modal>
    </PageHeader>
  );
}
