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
import PageHeader from "../components/layout/PageHeader";
import { Patient, patientsApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

const PAGE_SIZE = 25;

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

  const pagesCount = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  async function submit() {
    if (!draft.first_name || !draft.last_name) return;
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
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setShowNew(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={submit}>Create</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Form>
          <SpaceBetween size="m">
            <FormField label="First name">
              <Input value={draft.first_name ?? ""} onChange={(e) => setDraft({ ...draft, first_name: e.detail.value })} />
            </FormField>
            <FormField label="Last name">
              <Input value={draft.last_name ?? ""} onChange={(e) => setDraft({ ...draft, last_name: e.detail.value })} />
            </FormField>
            <FormField label="Date of birth" description="YYYY-MM-DD">
              <Input value={draft.dob ?? ""} onChange={(e) => setDraft({ ...draft, dob: e.detail.value })} />
            </FormField>
            <FormField label="Email">
              <Input type="email" value={draft.email ?? ""} onChange={(e) => setDraft({ ...draft, email: e.detail.value })} />
            </FormField>
            <FormField label="Phone">
              <Input value={draft.phone ?? ""} onChange={(e) => setDraft({ ...draft, phone: e.detail.value })} />
            </FormField>
          </SpaceBetween>
        </Form>
      </Modal>
    </PageHeader>
  );
}
