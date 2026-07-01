import { useCallback, useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Select, { SelectProps } from "@cloudscape-design/components/select";
import DatePicker from "@cloudscape-design/components/date-picker";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Modal from "@cloudscape-design/components/modal";
import Textarea from "@cloudscape-design/components/textarea";
import PageHeader from "../components/layout/PageHeader";
import { Appointment, appointmentsApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

const STATUS_OPTIONS: SelectProps.Option[] = [
  { label: "All", value: "" },
  { label: "Scheduled", value: "scheduled" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Checked in", value: "checked_in" },
  { label: "Completed", value: "completed" },
  { label: "Canceled", value: "canceled" },
  { label: "No-show", value: "no_show" },
];

function statusIndicator(status: string) {
  switch (status) {
    case "completed": return <StatusIndicator type="success">Completed</StatusIndicator>;
    case "canceled": return <StatusIndicator type="stopped">Canceled</StatusIndicator>;
    case "no_show": return <StatusIndicator type="error">No-show</StatusIndicator>;
    case "checked_in": return <StatusIndicator type="in-progress">Checked in</StatusIndicator>;
    case "confirmed": return <StatusIndicator type="pending">Confirmed</StatusIndicator>;
    default: return <StatusIndicator type="info">{status}</StatusIndicator>;
  }
}

export default function AppointmentsPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<SelectProps.Option>(STATUS_OPTIONS[0]);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    appointmentsApi
      .list({
        status: status.value || undefined,
        from_ts: from ? new Date(from).toISOString() : undefined,
        to_ts: to ? new Date(to + "T23:59:59").toISOString() : undefined,
      })
      .then((r) => setItems(r.items ?? []))
      .catch(() => push({ type: "error", content: "Failed to load appointments" }))
      .finally(() => setLoading(false));
  }, [status, from, to, push]);

  useEffect(() => { load(); }, [load]);

  async function doCancel() {
    if (!cancelTarget) return;
    try {
      await appointmentsApi.cancel(cancelTarget.id, reason);
      push({ type: "success", content: "Appointment canceled" });
      setCancelTarget(null);
      setReason("");
      load();
    } catch {
      push({ type: "error", content: "Cancel failed" });
    }
  }

  return (
    <PageHeader title="Appointments" description="All appointments across providers and offices">
      <SpaceBetween size="l">
        <SpaceBetween direction="horizontal" size="s">
          <div style={{ minWidth: 180 }}>
            <Select selectedOption={status} options={STATUS_OPTIONS} onChange={(e) => setStatus(e.detail.selectedOption)} />
          </div>
          <DatePicker placeholder="From" value={from} onChange={({ detail }) => setFrom(detail.value)} />
          <DatePicker placeholder="To" value={to} onChange={({ detail }) => setTo(detail.value)} />
          <Button onClick={() => { setFrom(""); setTo(""); setStatus(STATUS_OPTIONS[0]); }}>Clear</Button>
        </SpaceBetween>
        <Table
          loading={loading}
          items={items}
          variant="full-page"
          stickyHeader
          columnDefinitions={[
            { id: "start", header: "Start", cell: (a) => new Date(a.start_at).toLocaleString(), sortingField: "start_at" },
            { id: "end", header: "End", cell: (a) => new Date(a.end_at).toLocaleTimeString() },
            { id: "patient", header: "Patient", cell: (a) => a.patient_id.slice(0, 8) },
            { id: "provider", header: "Provider", cell: (a) => a.provider_id.slice(0, 8) },
            { id: "status", header: "Status", cell: (a) => statusIndicator(a.status) },
            { id: "source", header: "Source", cell: (a) => a.source },
            {
              id: "actions",
              header: "",
              cell: (a) => a.status !== "canceled" && a.status !== "completed" ? (
                <Button variant="inline-link" onClick={() => setCancelTarget(a)}>Cancel</Button>
              ) : null,
            },
          ]}
          header={<Header counter={`(${items.length})`}>Appointments</Header>}
          empty={<Box textAlign="center" padding="l">No appointments match.</Box>}
        />
      </SpaceBetween>

      <Modal
        visible={!!cancelTarget}
        onDismiss={() => setCancelTarget(null)}
        header="Cancel appointment"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setCancelTarget(null)}>Keep</Button>
              <Button variant="primary" onClick={doCancel}>Cancel appointment</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <Textarea value={reason} onChange={(e) => setReason(e.detail.value)} placeholder="Reason (required by policy)" />
      </Modal>
    </PageHeader>
  );
}
