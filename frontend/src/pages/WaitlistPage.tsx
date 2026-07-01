import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Box from "@cloudscape-design/components/box";
import PageHeader from "../components/layout/PageHeader";
import { waitlistApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

interface WaitlistEntry {
  id: string;
  patient_name?: string;
  appointment_type?: string;
  provider_pref?: string | null;
  earliest?: string | null;
  latest?: string | null;
  status: string;
  notified_at?: string | null;
}

export default function WaitlistPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<WaitlistEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    waitlistApi
      .list()
      .then((r: unknown) => setItems(((r as { items?: WaitlistEntry[] }).items) ?? []))
      .catch(() => push({ type: "error", content: "Failed to load waitlist" }))
      .finally(() => setLoading(false));
  }, [push]);

  return (
    <PageHeader title="Waitlist" description="Patients waiting for earlier slots — auto-notified on cancellations">
      <Table
        loading={loading}
        items={items}
        variant="full-page"
        stickyHeader
        columnDefinitions={[
          { id: "patient", header: "Patient", cell: (i) => i.patient_name ?? i.id.slice(0, 8) },
          { id: "type", header: "Appointment type", cell: (i) => i.appointment_type ?? "—" },
          { id: "provider", header: "Provider preference", cell: (i) => i.provider_pref ?? "Any" },
          { id: "earliest", header: "Earliest", cell: (i) => i.earliest ?? "—" },
          { id: "latest", header: "Latest", cell: (i) => i.latest ?? "—" },
          { id: "status", header: "Status", cell: (i) => i.status },
          { id: "notified", header: "Last notified", cell: (i) => i.notified_at ?? "—" },
        ]}
        header={<Header counter={`(${items.length})`}>Waitlist</Header>}
        empty={<Box textAlign="center" padding="l">Waitlist is empty.</Box>}
      />
    </PageHeader>
  );
}
