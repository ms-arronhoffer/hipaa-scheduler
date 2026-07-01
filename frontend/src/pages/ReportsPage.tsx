import { useEffect, useState } from "react";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Box from "@cloudscape-design/components/box";
import DatePicker from "@cloudscape-design/components/date-picker";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import Spinner from "@cloudscape-design/components/spinner";
import PageHeader from "../components/layout/PageHeader";
import { reportsApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

function isoStart(v: string) { return v ? new Date(v + "T00:00:00").toISOString() : undefined; }
function isoEnd(v: string) { return v ? new Date(v + "T23:59:59").toISOString() : undefined; }

interface UtilizationRow { provider_id: string; provider_name?: string; scheduled_min: number; available_min: number; utilization_pct: number }
interface NoShowRow { provider_id: string; provider_name?: string; total: number; no_shows: number; no_show_pct: number }

export default function ReportsPage() {
  const { push } = useFlash();
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [util, setUtil] = useState<UtilizationRow[]>([]);
  const [noShow, setNoShow] = useState<NoShowRow[]>([]);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      const [u, n] = await Promise.all([
        reportsApi.utilization({ from_ts: isoStart(from), to_ts: isoEnd(to) }) as Promise<{ items?: UtilizationRow[] }>,
        reportsApi.noShows({ from_ts: isoStart(from), to_ts: isoEnd(to) }) as Promise<{ items?: NoShowRow[] }>,
      ]);
      setUtil(u.items ?? []);
      setNoShow(n.items ?? []);
    } catch {
      push({ type: "error", content: "Report failed" });
    } finally { setLoading(false); }
  }

  useEffect(() => { run(); /* eslint-disable-next-line */ }, []);

  return (
    <PageHeader title="Reports" description="Utilization and no-show summaries">
      <SpaceBetween size="l">
        <Container>
          <ColumnLayout columns={3}>
            <div>
              <Box variant="awsui-key-label">From</Box>
              <DatePicker value={from} onChange={({ detail }) => setFrom(detail.value)} />
            </div>
            <div>
              <Box variant="awsui-key-label">To</Box>
              <DatePicker value={to} onChange={({ detail }) => setTo(detail.value)} />
            </div>
            <div style={{ display: "flex", alignItems: "end" }}>
              <Button variant="primary" onClick={run} loading={loading}>Run</Button>
            </div>
          </ColumnLayout>
        </Container>

        {loading ? (
          <Box textAlign="center" padding="xxl"><Spinner size="large" /></Box>
        ) : (
          <>
            <Container header={<Header variant="h2">Provider utilization</Header>}>
              <Table
                items={util}
                columnDefinitions={[
                  { id: "provider", header: "Provider", cell: (r) => r.provider_name ?? r.provider_id.slice(0, 8) },
                  { id: "avail", header: "Available (min)", cell: (r) => r.available_min },
                  { id: "sched", header: "Scheduled (min)", cell: (r) => r.scheduled_min },
                  { id: "pct", header: "Utilization %", cell: (r) => `${Math.round(r.utilization_pct)}%` },
                ]}
                empty={<Box textAlign="center" padding="l">No data.</Box>}
              />
            </Container>

            <Container header={<Header variant="h2">No-show rate</Header>}>
              <Table
                items={noShow}
                columnDefinitions={[
                  { id: "provider", header: "Provider", cell: (r) => r.provider_name ?? r.provider_id.slice(0, 8) },
                  { id: "total", header: "Total appts", cell: (r) => r.total },
                  { id: "no", header: "No-shows", cell: (r) => r.no_shows },
                  { id: "pct", header: "No-show %", cell: (r) => `${Math.round(r.no_show_pct)}%` },
                ]}
                empty={<Box textAlign="center" padding="l">No data.</Box>}
              />
            </Container>
          </>
        )}
      </SpaceBetween>
    </PageHeader>
  );
}
