import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Table from "@cloudscape-design/components/table";
import Button from "@cloudscape-design/components/button";
import Header from "@cloudscape-design/components/header";
import Pagination from "@cloudscape-design/components/pagination";
import TextFilter from "@cloudscape-design/components/text-filter";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import PageHeader from "../components/layout/PageHeader";
import { officesApi, Patient, PatientAddress, patientsApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

const PAGE_SIZE = 25;

const SEX_OPTIONS: SelectProps.Option[] = [
  { label: "Female", value: "F" },
  { label: "Male", value: "M" },
  { label: "Other", value: "O" },
  { label: "Unknown", value: "U" },
];

interface OfficeOption {
  id: string;
  name: string;
}

export default function PatientsPage() {
  const nav = useNavigate();
  const { push } = useFlash();
  const [items, setItems] = useState<Patient[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [draft, setDraft] = useState<Partial<Patient>>({});
  const [saving, setSaving] = useState(false);
  const [offices, setOffices] = useState<OfficeOption[]>([]);

  const load = useCallback(() => {
    setLoading(true);
    patientsApi
      .list({ q: q || undefined, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE })
      .then((res) => {
        setItems(res.items ?? []);
        setTotal(res.total ?? 0);
      })
      .catch(() => push({ type: "error", content: "Failed to load patients" }))
      .finally(() => setLoading(false));
  }, [q, page, push]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    officesApi
      .list()
      .then((r: unknown) => {
        const rows = ((r as { items?: OfficeOption[] }).items ?? (r as OfficeOption[])) || [];
        setOffices(rows.map((o) => ({ id: o.id, name: o.name })));
      })
      .catch(() => { /* office dropdown is optional; ignore load failures */ });
  }, []);

  const pagesCount = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  function updateAddress(patch: Partial<PatientAddress>) {
    setDraft((d) => ({ ...d, address: { ...(d.address ?? {}), ...patch } }));
  }

  const officeOptions: SelectProps.Option[] = useMemo(
    () => offices.map((o) => ({ label: o.name, value: o.id })),
    [offices],
  );

  const canSubmit = Boolean(draft.mrn && draft.first_name && draft.last_name && draft.dob);

  async function submit() {
    if (!canSubmit) return;
    setSaving(true);
    try {
      const p = await patientsApi.create(draft);
      push({ type: "success", content: "Patient created" });
      setShowNew(false);
      setDraft({});
      nav(`/patients/${p.id}`);
    } catch {
      push({ type: "error", content: "Could not create patient" });
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageHeader
      title="Patients"
      description="Search and manage patient records"
      actions={<Button variant="primary" onClick={() => setShowNew(true)}>New patient</Button>}
    >
      <Table
        loading={loading}
        loadingText="Loading patients"
        items={items}
        variant="full-page"
        stickyHeader
        onRowClick={({ detail }) => nav(`/patients/${detail.item.id}`)}
        columnDefinitions={[
          { id: "mrn", header: "MRN", cell: (i) => i.mrn ?? "—" },
          { id: "name", header: "Name", cell: (i) => `${i.last_name}, ${i.first_name}` },
          { id: "dob", header: "DOB", cell: (i) => i.dob ?? "—" },
          { id: "email", header: "Email", cell: (i) => i.email ?? "—" },
          { id: "phone", header: "Phone", cell: (i) => i.phone ?? "—" },
          {
            id: "sms",
            header: "SMS opted in",
            cell: (i) => (i.sms_opt_in_at ? "Yes" : "No"),
          },
        ]}
        header={<Header counter={`(${total})`}>Patients</Header>}
        filter={
          <TextFilter
            filteringText={q}
            filteringPlaceholder="Search by name, MRN, email"
            onChange={({ detail }) => { setPage(1); setQ(detail.filteringText); }}
          />
        }
        pagination={
          <Pagination
            currentPageIndex={page}
            pagesCount={pagesCount}
            onChange={({ detail }) => setPage(detail.currentPageIndex)}
          />
        }
        empty={<Box textAlign="center" padding="l">No patients yet.</Box>}
      />

      <Modal
        visible={showNew}
        onDismiss={() => setShowNew(false)}
        header="New patient"
        size="large"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowNew(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} disabled={!canSubmit} onClick={submit}>Create</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Form>
          <SpaceBetween size="l">
            <Container header={<Header variant="h3">Identity</Header>}>
              <SpaceBetween size="m">
                <FormField label="MRN" description="Medical record number (required, unique per practice)">
                  <Input value={draft.mrn ?? ""} onChange={(e) => setDraft({ ...draft, mrn: e.detail.value })} />
                </FormField>
                <ColumnLayout columns={3}>
                  <FormField label="First name">
                    <Input value={draft.first_name ?? ""} onChange={(e) => setDraft({ ...draft, first_name: e.detail.value })} />
                  </FormField>
                  <FormField label="Middle name">
                    <Input value={draft.middle_name ?? ""} onChange={(e) => setDraft({ ...draft, middle_name: e.detail.value })} />
                  </FormField>
                  <FormField label="Last name">
                    <Input value={draft.last_name ?? ""} onChange={(e) => setDraft({ ...draft, last_name: e.detail.value })} />
                  </FormField>
                </ColumnLayout>
                <ColumnLayout columns={2}>
                  <FormField label="Date of birth" description="YYYY-MM-DD">
                    <Input value={draft.dob ?? ""} onChange={(e) => setDraft({ ...draft, dob: e.detail.value })} />
                  </FormField>
                  <FormField label="Sex">
                    <Select
                      selectedOption={SEX_OPTIONS.find((o) => o.value === draft.sex) ?? null}
                      options={SEX_OPTIONS}
                      placeholder="Select"
                      onChange={(e) => setDraft({ ...draft, sex: e.detail.selectedOption?.value ?? null })}
                    />
                  </FormField>
                </ColumnLayout>
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h3">Contact</Header>}>
              <SpaceBetween size="m">
                <ColumnLayout columns={2}>
                  <FormField label="Email">
                    <Input type="email" value={draft.email ?? ""} onChange={(e) => setDraft({ ...draft, email: e.detail.value })} />
                  </FormField>
                  <FormField label="Phone">
                    <Input value={draft.phone ?? ""} onChange={(e) => setDraft({ ...draft, phone: e.detail.value })} />
                  </FormField>
                </ColumnLayout>
                <FormField label="Address line 1">
                  <Input value={draft.address?.line1 ?? ""} onChange={(e) => updateAddress({ line1: e.detail.value })} />
                </FormField>
                <FormField label="Address line 2">
                  <Input value={draft.address?.line2 ?? ""} onChange={(e) => updateAddress({ line2: e.detail.value })} />
                </FormField>
                <ColumnLayout columns={3}>
                  <FormField label="City">
                    <Input value={draft.address?.city ?? ""} onChange={(e) => updateAddress({ city: e.detail.value })} />
                  </FormField>
                  <FormField label="State">
                    <Input value={draft.address?.state ?? ""} onChange={(e) => updateAddress({ state: e.detail.value })} />
                  </FormField>
                  <FormField label="Postal code">
                    <Input value={draft.address?.postal_code ?? ""} onChange={(e) => updateAddress({ postal_code: e.detail.value })} />
                  </FormField>
                </ColumnLayout>
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h3">Care preferences</Header>}>
              <FormField label="Preferred office">
                <Select
                  selectedOption={officeOptions.find((o) => o.value === draft.preferred_office_id) ?? null}
                  options={officeOptions}
                  placeholder="No preference"
                  empty="No offices configured"
                  onChange={(e) => setDraft({ ...draft, preferred_office_id: e.detail.selectedOption?.value ?? null })}
                />
              </FormField>
            </Container>
          </SpaceBetween>
        </Form>
      </Modal>
    </PageHeader>
  );
}
