import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import { publicApi, Appointment } from "../api/publicBooking";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

function statusIndicator(s: string) {
  switch (s) {
    case "scheduled":
      return <StatusIndicator type="pending">Scheduled</StatusIndicator>;
    case "confirmed":
      return <StatusIndicator type="success">Confirmed</StatusIndicator>;
    case "checked_in":
      return <StatusIndicator type="in-progress">Checked in</StatusIndicator>;
    case "completed":
      return <StatusIndicator type="success">Completed</StatusIndicator>;
    case "canceled":
      return <StatusIndicator type="stopped">Canceled</StatusIndicator>;
    case "no_show":
      return <StatusIndicator type="error">No-show</StatusIndicator>;
    default:
      return <StatusIndicator type="info">{s}</StatusIndicator>;
  }
}

function isUpcoming(a: Appointment): boolean {
  return (
    (a.status === "scheduled" || a.status === "confirmed") &&
    new Date(a.start_at).getTime() > Date.now()
  );
}

export default function MyAppointmentsPage() {
  const { push } = useFlash();
  const [rows, setRows] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [toCancel, setToCancel] = useState<Appointment | null>(null);
  const [canceling, setCanceling] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      setRows(await publicApi.myAppointments());
    } catch {
      push({ type: "error", content: "Could not load appointments." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function doCancel() {
    if (!toCancel) return;
    setCanceling(true);
    setErr(null);
    try {
      await publicApi.cancel(toCancel.id);
      setToCancel(null);
      push({ type: "success", content: "Appointment canceled." });
      await reload();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setErr(err.response?.data?.detail ?? "Cancellation failed.");
    } finally {
      setCanceling(false);
    }
  }

  return (
    <PageHeader
      title="My appointments"
      description="Upcoming and past visits."
      actions={<Button iconName="refresh" onClick={reload} loading={loading} />}
    >
      <Table
        variant="container"
        loading={loading}
        loadingText="Loading appointments"
        items={rows}
        columnDefinitions={[
          {
            id: "when",
            header: "When",
            cell: (r) => new Date(r.start_at).toLocaleString(),
          },
          { id: "duration", header: "Duration", cell: (r) => `${r.duration_min} min` },
          { id: "status", header: "Status", cell: (r) => statusIndicator(r.status) },
          { id: "source", header: "Booked via", cell: (r) => r.source },
          {
            id: "actions",
            header: "",
            cell: (r) =>
              isUpcoming(r) ? (
                <Button variant="inline-link" onClick={() => setToCancel(r)}>
                  Cancel
                </Button>
              ) : null,
          },
        ]}
        empty={
          <Box textAlign="center" color="inherit">
            <b>No appointments yet</b>
          </Box>
        }
      />

      <Modal
        visible={!!toCancel}
        onDismiss={() => setToCancel(null)}
        header="Cancel appointment"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setToCancel(null)} disabled={canceling}>
                Keep it
              </Button>
              <Button variant="primary" loading={canceling} onClick={doCancel}>
                Cancel appointment
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          {err && <Alert type="error">{err}</Alert>}
          {toCancel && (
            <Box>
              Are you sure you want to cancel your appointment on{" "}
              <b>{new Date(toCancel.start_at).toLocaleString()}</b>? Late cancellations
              may be subject to the office's cancellation policy.
            </Box>
          )}
        </SpaceBetween>
      </Modal>
    </PageHeader>
  );
}
