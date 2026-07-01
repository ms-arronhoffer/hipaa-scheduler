import { useEffect, useState } from "react";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { adminApi, SystemHealth } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <div>{value}</div>
    </div>
  );
}

function ok(v: boolean) {
  return v ? (
    <StatusIndicator type="success">OK</StatusIndicator>
  ) : (
    <StatusIndicator type="error">Down</StatusIndicator>
  );
}

export default function SystemHealthPage() {
  const { push } = useFlash();
  const [h, setH] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true);
    try {
      setH(await adminApi.systemHealth());
    } catch {
      push({ type: "error", content: "Failed to load system health" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => void reload(), 30_000);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PageHeader
      title="System health"
      description="Live view of core subsystems. Refreshes every 30 seconds."
      actions={<Button iconName="refresh" onClick={reload} loading={loading} />}
    >
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Database</Header>}>
          <ColumnLayout columns={2} variant="text-grid">
            <KV label="Status" value={h ? ok(h.database.ok) : "—"} />
            <KV label="Latency" value={h ? `${h.database.latency_ms} ms` : "—"} />
          </ColumnLayout>
        </Container>

        <Container header={<Header variant="h2">Scheduler</Header>}>
          <ColumnLayout columns={3} variant="text-grid">
            <KV label="Status" value={h ? ok(h.scheduler.ok) : "—"} />
            <KV label="Jobs registered" value={h?.scheduler.jobs_registered ?? "—"} />
            <KV
              label="Next run"
              value={
                h?.scheduler.next_run_at ? new Date(h.scheduler.next_run_at).toLocaleString() : "—"
              }
            />
          </ColumnLayout>
        </Container>

        <Container header={<Header variant="h2">Webhook queue</Header>}>
          <ColumnLayout columns={2} variant="text-grid">
            <KV label="Pending" value={h?.webhook_queue.pending ?? "—"} />
            <KV
              label="Failed (24h)"
              value={
                h ? (
                  h.webhook_queue.failed_last_24h > 0 ? (
                    <StatusIndicator type="warning">{h.webhook_queue.failed_last_24h}</StatusIndicator>
                  ) : (
                    <StatusIndicator type="success">0</StatusIndicator>
                  )
                ) : (
                  "—"
                )
              }
            />
          </ColumnLayout>
        </Container>

        <Container header={<Header variant="h2">Object storage</Header>}>
          <ColumnLayout columns={1} variant="text-grid">
            <KV label="Status" value={h ? ok(h.storage.ok) : "—"} />
          </ColumnLayout>
        </Container>

        <Container header={<Header variant="h2">Build</Header>}>
          <ColumnLayout columns={3} variant="text-grid">
            <KV label="Version" value={h ? <code>{h.build.version}</code> : "—"} />
            <KV label="Commit" value={h ? <code>{h.build.commit}</code> : "—"} />
            <KV
              label="Started"
              value={h ? new Date(h.build.started_at).toLocaleString() : "—"}
            />
          </ColumnLayout>
        </Container>
      </SpaceBetween>
    </PageHeader>
  );
}
