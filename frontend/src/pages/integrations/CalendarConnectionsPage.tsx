import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import PageHeader from "../../components/layout/PageHeader";
import { calendarConnectionsApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface CalendarConnection {
  id: string;
  provider: "google" | "o365" | "caldav";
  account_email: string;
  status: string;
  last_synced_at?: string | null;
  provider_user_id?: string;
}

function connectHref(provider: "google" | "o365") {
  return `/api/v1/calendar-connections/oauth/${provider}/start`;
}

export default function CalendarConnectionsPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<CalendarConnection[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    calendarConnectionsApi.list()
      .then((r: unknown) => setItems(((r as { items?: CalendarConnection[] }).items) ?? (r as CalendarConnection[])))
      .catch(() => push({ type: "error", content: "Failed to load connections" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function disconnect(c: CalendarConnection) {
    if (!confirm(`Disconnect ${c.account_email}? Two-way sync will stop.`)) return;
    try {
      await calendarConnectionsApi.delete(c.id);
      push({ type: "success", content: "Disconnected" });
      load();
    } catch {
      push({ type: "error", content: "Disconnect failed" });
    }
  }

  return (
    <PageHeader title="Calendar sync" description="Two-way sync with provider calendars (Google, Outlook/O365)">
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Connect a calendar</Header>}>
          <SpaceBetween direction="horizontal" size="s">
            <Button iconName="external" href={connectHref("google")}>Connect Google</Button>
            <Button iconName="external" href={connectHref("o365")}>Connect Outlook / O365</Button>
          </SpaceBetween>
        </Container>

        <Table
          loading={loading}
          items={items}
          columnDefinitions={[
            { id: "provider", header: "Provider", cell: (c) => c.provider.toUpperCase() },
            { id: "account", header: "Account", cell: (c) => c.account_email },
            {
              id: "status",
              header: "Status",
              cell: (c) => c.status === "connected"
                ? <StatusIndicator type="success">Connected</StatusIndicator>
                : <StatusIndicator type="warning">{c.status}</StatusIndicator>,
            },
            { id: "synced", header: "Last synced", cell: (c) => c.last_synced_at ? new Date(c.last_synced_at).toLocaleString() : "Never" },
            { id: "actions", header: "", cell: (c) => <Button variant="inline-link" onClick={() => disconnect(c)}>Disconnect</Button> },
          ]}
          header={<Header counter={`(${items.length})`}>Connected calendars</Header>}
          empty={<Box textAlign="center" padding="l">No calendars connected yet.</Box>}
        />
      </SpaceBetween>
    </PageHeader>
  );
}
