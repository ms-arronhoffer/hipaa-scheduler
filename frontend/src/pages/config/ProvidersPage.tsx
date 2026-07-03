import { useEffect, useMemo, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import PageHeader from "../../components/layout/PageHeader";
import { providersApi, usersApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface Provider {
  id: string;
  user_id: string;
  display_name?: string;
  email?: string;
  npi?: string | null;
  specialty?: string | null;
  bookable: boolean;
}

interface StaffUser {
  id: string;
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  roles: string[];
}

export default function ProvidersPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<StaffUser[]>([]);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [selectedUser, setSelectedUser] = useState<SelectProps.Option | null>(null);
  const [npi, setNpi] = useState("");
  const [specialty, setSpecialty] = useState("");

  function load() {
    setLoading(true);
    providersApi.list()
      .then((r: unknown) => setItems(((r as { items?: Provider[] }).items) ?? (r as Provider[])))
      .catch(() => push({ type: "error", content: "Failed to load providers" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  useEffect(() => {
    usersApi.list()
      .then((r: unknown) => setUsers(((r as { items?: StaffUser[] }).items) ?? (r as StaffUser[])))
      .catch(() => { /* provider creation still works without the picker cache */ });
  }, []);

  // Only offer staff users who aren't already a provider.
  const userOptions = useMemo<SelectProps.Option[]>(() => {
    const existing = new Set(items.map((p) => p.user_id));
    return users
      .filter((u) => !existing.has(u.id))
      .map((u) => {
        const name = `${u.first_name ?? ""} ${u.last_name ?? ""}`.trim();
        return { value: u.id, label: name ? `${name} (${u.email})` : u.email };
      });
  }, [users, items]);

  function openCreate() {
    setSelectedUser(null);
    setNpi("");
    setSpecialty("");
    setCreating(true);
  }

  async function submit() {
    if (!selectedUser?.value) return;
    setSaving(true);
    try {
      await providersApi.create({
        user_id: selectedUser.value,
        npi: npi || undefined,
        specialty: specialty || undefined,
      });
      push({ type: "success", content: "Provider added" });
      setCreating(false);
      load();
    } catch {
      push({ type: "error", content: "Failed to add provider" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageHeader
      title="Providers"
      description="Bookable clinicians on your team"
      actions={<Button variant="primary" onClick={openCreate}>New provider</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (p) => p.display_name ?? p.email ?? p.id.slice(0, 8) },
          { id: "email", header: "Email", cell: (p) => p.email ?? "\u2014" },
          { id: "npi", header: "NPI", cell: (p) => p.npi ?? "\u2014" },
          { id: "specialty", header: "Specialty", cell: (p) => p.specialty ?? "\u2014" },
          { id: "bookable", header: "Bookable", cell: (p) => (p.bookable ? "Yes" : "No") },
        ]}
        header={<Header counter={`(${items.length})`}>Providers</Header>}
        empty={<Box textAlign="center" padding="l">No providers configured. Create a staff user with the "provider" role first.</Box>}
      />

      <Modal
        visible={creating}
        onDismiss={() => setCreating(false)}
        header="New provider"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setCreating(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} disabled={!selectedUser} onClick={submit}>Add provider</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Form>
          <SpaceBetween size="m">
            <FormField label="Staff user" description="Add an existing staff user as a bookable provider. Create the user first under Staff users if needed.">
              <Select
                selectedOption={selectedUser}
                options={userOptions}
                onChange={(e) => setSelectedUser(e.detail.selectedOption)}
                placeholder="Select a staff user"
                empty="No eligible staff users. Create one under Staff users."
                filteringType="auto"
              />
            </FormField>
            <FormField label="NPI" description="Optional">
              <Input value={npi} onChange={(e) => setNpi(e.detail.value)} />
            </FormField>
            <FormField label="Specialty" description="Optional">
              <Input value={specialty} onChange={(e) => setSpecialty(e.detail.value)} />
            </FormField>
          </SpaceBetween>
        </Form>
      </Modal>
    </PageHeader>
  );
}
