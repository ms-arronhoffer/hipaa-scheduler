import { useCallback, useEffect, useMemo, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Toggle from "@cloudscape-design/components/toggle";
import Input from "@cloudscape-design/components/input";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import Pagination from "@cloudscape-design/components/pagination";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import Badge from "@cloudscape-design/components/badge";
import PageHeader from "../components/layout/PageHeader";
import { ActivityLogEntry, activityLogApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

const PAGE_SIZE = 50;

const ENTITY_OPTIONS: SelectProps.Option[] = [
  { label: "All entities", value: "" },
  { label: "Patient", value: "patient" },
  { label: "Appointment", value: "appointment" },
  { label: "IntakeSubmission", value: "intake_submission" },
  { label: "Document", value: "document" },
  { label: "InsurancePolicy", value: "insurance_policy" },
  { label: "User", value: "user" },
];

export default function ActivityLogPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<ActivityLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [entity, setEntity] = useState<SelectProps.Option>(ENTITY_OPTIONS[0]);
  const [phiOnly, setPhiOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    activityLogApi
      .list({
        entity_type: entity.value || undefined,
        phi_only: phiOnly || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      })
      .then((r) => {
        const rows = r.items ?? [];
        const filtered = q
          ? rows.filter((x) =>
              (x.actor_email ?? "").toLowerCase().includes(q.toLowerCase()) ||
              x.entity_type.toLowerCase().includes(q.toLowerCase()) ||
              x.action.toLowerCase().includes(q.toLowerCase())
            )
          : rows;
        setItems(filtered);
        setTotal(r.total ?? filtered.length);
      })
      .catch(() => push({ type: "error", content: "Failed to load audit log" }))
      .finally(() => setLoading(false));
  }, [entity, phiOnly, page, q, push]);

  useEffect(() => { load(); }, [load]);

  const pagesCount = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  return (
    <PageHeader
      title="PHI access log"
      description="Immutable audit trail — every PHI access is recorded and retained for six years"
    >
      <SpaceBetween size="l">
        <SpaceBetween direction="horizontal" size="s">
          <div style={{ minWidth: 220 }}>
            <Select selectedOption={entity} options={ENTITY_OPTIONS} onChange={(e) => { setPage(1); setEntity(e.detail.selectedOption); }} />
          </div>
          <div style={{ minWidth: 260 }}>
            <Input value={q} onChange={(e) => { setPage(1); setQ(e.detail.value); }} placeholder="Search actor, entity, action" />
          </div>
          <Toggle checked={phiOnly} onChange={(e) => { setPage(1); setPhiOnly(e.detail.checked); }}>PHI-only</Toggle>
        </SpaceBetween>

        <Table
          loading={loading}
          items={items}
          variant="full-page"
          stickyHeader
          columnDefinitions={[
            { id: "when", header: "When", cell: (r) => new Date(r.created_at).toLocaleString() },
            { id: "actor", header: "Actor", cell: (r) => `${r.actor_email ?? r.actor_type} (${r.actor_type})` },
            { id: "action", header: "Action", cell: (r) => r.action },
            { id: "entity", header: "Entity", cell: (r) => `${r.entity_type}${r.entity_id ? ` · ${r.entity_id.slice(0, 8)}` : ""}` },
            { id: "phi", header: "PHI", cell: (r) => r.phi_accessed ? <Badge color="red">Yes</Badge> : <Badge color="grey">No</Badge> },
            { id: "ip", header: "IP", cell: (r) => r.ip ?? "—" },
          ]}
          header={<Header counter={`(${total})`}>Audit entries</Header>}
          pagination={
            <Pagination currentPageIndex={page} pagesCount={pagesCount} onChange={({ detail }) => setPage(detail.currentPageIndex)} />
          }
          empty={<Box textAlign="center" padding="l">No entries match the current filter.</Box>}
        />
      </SpaceBetween>
    </PageHeader>
  );
}
