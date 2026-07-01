import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Button from "@cloudscape-design/components/button";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Box from "@cloudscape-design/components/box";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Multiselect, { MultiselectProps } from "@cloudscape-design/components/multiselect";
import Alert from "@cloudscape-design/components/alert";
import Badge from "@cloudscape-design/components/badge";
import PageHeader from "../../components/layout/PageHeader";
import { webhooksApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface Webhook {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  last_delivery_at?: string | null;
  last_status?: number | null;
}

interface Delivery {
  id: string;
  event: string;
  status_code: number | null;
  attempt: number;
  succeeded: boolean;
  scheduled_at: string;
  delivered_at: string | null;
}

const EVENT_OPTIONS: MultiselectProps.Option[] = [
  { label: "appointment.created", value: "appointment.created" },
  { label: "appointment.updated", value: "appointment.updated" },
  { label: "appointment.canceled", value: "appointment.canceled" },
  { label: "appointment.no_show", value: "appointment.no_show" },
  { label: "appointment.checked_in", value: "appointment.checked_in" },
  { label: "patient.created", value: "patient.created" },
  { label: "patient.updated", value: "patient.updated" },
  { label: "intake.submitted", value: "intake.submitted" },
  { label: "waitlist.filled", value: "waitlist.filled" },
];

export default function WebhooksPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<Webhook[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [url, setUrl] = useState("");
  const [events, setEvents] = useState<MultiselectProps.Option[]>([]);
  const [saving, setSaving] = useState(false);
  const [rotatedSecret, setRotatedSecret] = useState<string | null>(null);
  const [deliveriesFor, setDeliveriesFor] = useState<Webhook | null>(null);
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);

  function load() {
    setLoading(true);
    webhooksApi.list()
      .then((r: unknown) => setItems(((r as { items?: Webhook[] }).items) ?? (r as Webhook[])))
      .catch(() => push({ type: "error", content: "Failed to load webhooks" }))
      .finally(() => setLoading(false));
  }
  useEffect(load, [push]);

  async function create() {
    setSaving(true);
    try {
      await webhooksApi.create({ url, events: events.map((e) => e.value!) });
      push({ type: "success", content: "Webhook created" });
      setCreating(false);
      setUrl("");
      setEvents([]);
      load();
    } catch {
      push({ type: "error", content: "Create failed" });
    } finally { setSaving(false); }
  }

  async function rotate(w: Webhook) {
    if (!confirm(`Rotate signing secret for ${w.url}? The old secret will stop working immediately.`)) return;
    try {
      const res = await webhooksApi.rotate(w.id);
      setRotatedSecret(res.secret);
    } catch {
      push({ type: "error", content: "Rotate failed" });
    }
  }

  async function openDeliveries(w: Webhook) {
    setDeliveriesFor(w);
    try {
      const r = await webhooksApi.deliveries(w.id) as { items?: Delivery[] };
      setDeliveries(r.items ?? []);
    } catch {
      push({ type: "error", content: "Failed to load deliveries" });
    }
  }

  async function retry(delivery: Delivery) {
    if (!deliveriesFor) return;
    try {
      await webhooksApi.retry(deliveriesFor.id, delivery.id);
      push({ type: "success", content: "Retry queued" });
      openDeliveries(deliveriesFor);
    } catch {
      push({ type: "error", content: "Retry failed" });
    }
  }

  return (
    <PageHeader
      title="Webhooks"
      description="HMAC-signed HTTPS POSTs on scheduling events. Failed deliveries retry with exponential backoff."
      actions={<Button variant="primary" onClick={() => setCreating(true)}>New webhook</Button>}
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "url", header: "URL", cell: (w) => w.url },
          { id: "events", header: "Events", cell: (w) => w.events.length },
          { id: "active", header: "Active", cell: (w) => (w.active ? "Yes" : "No") },
          {
            id: "last",
            header: "Last delivery",
            cell: (w) => w.last_delivery_at ? (
              <SpaceBetween direction="horizontal" size="xs">
                <span>{new Date(w.last_delivery_at).toLocaleString()}</span>
                {w.last_status && <Badge color={w.last_status < 300 ? "green" : "red"}>{w.last_status}</Badge>}
              </SpaceBetween>
            ) : "Never",
          },
          {
            id: "actions",
            header: "",
            cell: (w) => (
              <SpaceBetween direction="horizontal" size="xs">
                <Button variant="inline-link" onClick={() => openDeliveries(w)}>Deliveries</Button>
                <Button variant="inline-link" onClick={() => rotate(w)}>Rotate secret</Button>
              </SpaceBetween>
            ),
          },
        ]}
        header={<Header counter={`(${items.length})`}>Webhooks</Header>}
        empty={<Box textAlign="center" padding="l">No webhooks yet.</Box>}
      />

      <Modal
        visible={creating}
        onDismiss={() => setCreating(false)}
        header="New webhook"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button onClick={() => setCreating(false)}>Cancel</Button>
              <Button variant="primary" loading={saving} onClick={create} disabled={!url || events.length === 0}>Create</Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <FormField label="Delivery URL" description="Must be HTTPS">
            <Input value={url} onChange={(e) => setUrl(e.detail.value)} placeholder="https://example.com/hooks/scheduler" />
          </FormField>
          <FormField label="Events">
            <Multiselect selectedOptions={events} options={EVENT_OPTIONS} onChange={({ detail }) => setEvents([...detail.selectedOptions])} />
          </FormField>
        </SpaceBetween>
      </Modal>

      <Modal
        visible={!!rotatedSecret}
        onDismiss={() => setRotatedSecret(null)}
        header="New signing secret"
        footer={<Box float="right"><Button variant="primary" onClick={() => setRotatedSecret(null)}>I've saved it</Button></Box>}
      >
        <SpaceBetween size="m">
          <Alert type="warning" header="Copy this secret now">Update your webhook receiver with this secret. It will not be shown again.</Alert>
          <Box variant="code" padding="s"><div style={{ wordBreak: "break-all", fontFamily: "monospace" }}>{rotatedSecret}</div></Box>
        </SpaceBetween>
      </Modal>

      <Modal
        visible={!!deliveriesFor}
        onDismiss={() => setDeliveriesFor(null)}
        header={`Recent deliveries — ${deliveriesFor?.url ?? ""}`}
        size="large"
      >
        <Table
          items={deliveries}
          columnDefinitions={[
            { id: "event", header: "Event", cell: (d) => d.event },
            { id: "attempt", header: "Attempt", cell: (d) => d.attempt },
            { id: "status", header: "Status", cell: (d) => d.status_code ?? "—" },
            { id: "delivered", header: "Delivered", cell: (d) => d.delivered_at ? new Date(d.delivered_at).toLocaleString() : "Pending" },
            {
              id: "actions",
              header: "",
              cell: (d) => !d.succeeded && <Button variant="inline-link" onClick={() => retry(d)}>Retry</Button>,
            },
          ]}
          empty={<Box textAlign="center" padding="l">No deliveries yet.</Box>}
        />
      </Modal>
    </PageHeader>
  );
}
