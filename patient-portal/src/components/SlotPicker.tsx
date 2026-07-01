import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import DatePicker from "@cloudscape-design/components/date-picker";
import FormField from "@cloudscape-design/components/form-field";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import {
  directoryApi,
  publicApi,
  AppointmentTypePublic,
  OfficePublic,
  ProviderPublic,
  Slot,
} from "../api/publicBooking";

export interface Selection {
  office: OfficePublic;
  provider: ProviderPublic;
  appointmentType: AppointmentTypePublic;
  slot: Slot;
}

interface Props {
  orgSlug: string;
  onSelected: (sel: Selection) => void;
  disabled?: boolean;
}

function fmtDayTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function addDaysISO(iso: string, days: number): string {
  const d = new Date(iso);
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function SlotPicker({ orgSlug, onSelected, disabled }: Props) {
  const [offices, setOffices] = useState<OfficePublic[]>([]);
  const [providers, setProviders] = useState<ProviderPublic[]>([]);
  const [types, setTypes] = useState<AppointmentTypePublic[]>([]);
  const [office, setOffice] = useState<OfficePublic | null>(null);
  const [provider, setProvider] = useState<ProviderPublic | null>(null);
  const [apptType, setApptType] = useState<AppointmentTypePublic | null>(null);
  const [rangeStart, setRangeStart] = useState<string>(todayISO());
  const [rangeEnd, setRangeEnd] = useState<string>(addDaysISO(todayISO(), 14));
  const [slots, setSlots] = useState<Slot[] | null>(null);
  const [loadingDir, setLoadingDir] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [o, t] = await Promise.all([
          directoryApi.offices(orgSlug),
          directoryApi.appointmentTypes(orgSlug),
        ]);
        if (!mounted) return;
        setOffices(o);
        setTypes(t);
        if (o.length === 1) setOffice(o[0]);
        if (t.length === 1) setApptType(t[0]);
      } catch {
        if (mounted) setErr("Could not load practice options.");
      } finally {
        if (mounted) setLoadingDir(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [orgSlug]);

  useEffect(() => {
    let mounted = true;
    if (!office) {
      setProviders([]);
      setProvider(null);
      return;
    }
    (async () => {
      try {
        const p = await directoryApi.providers(orgSlug, office.id);
        if (!mounted) return;
        setProviders(p);
        if (p.length === 1) setProvider(p[0]);
      } catch {
        if (mounted) setErr("Could not load providers.");
      }
    })();
    return () => {
      mounted = false;
    };
  }, [orgSlug, office]);

  async function loadSlots() {
    if (!office || !provider || !apptType) return;
    setLoadingSlots(true);
    setErr(null);
    setSlots(null);
    try {
      const s = await publicApi.listSlots({
        org_slug: orgSlug,
        office_id: office.id,
        provider_id: provider.id,
        appointment_type_id: apptType.id,
        range_start: new Date(rangeStart + "T00:00:00").toISOString(),
        range_end: new Date(rangeEnd + "T23:59:59").toISOString(),
      });
      setSlots(s);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setErr(err.response?.data?.detail ?? "Could not load slots.");
    } finally {
      setLoadingSlots(false);
    }
  }

  if (loadingDir) {
    return (
      <Box textAlign="center" padding="l">
        <Spinner />
      </Box>
    );
  }

  return (
    <SpaceBetween size="l">
      {err && <Alert type="error">{err}</Alert>}

      <FormField label="Office">
        <Select
          disabled={disabled}
          selectedOption={office ? { value: office.id, label: office.name } : null}
          options={offices.map((o) => ({ value: o.id, label: o.name }))}
          onChange={(e) => {
            const o = offices.find((x) => x.id === e.detail.selectedOption.value);
            setOffice(o ?? null);
            setSlots(null);
          }}
          placeholder="Select an office"
        />
      </FormField>

      <FormField label="Provider">
        <Select
          disabled={disabled || !office}
          selectedOption={
            provider ? { value: provider.id, label: provider.display_name } : null
          }
          options={providers.map((p) => ({
            value: p.id,
            label: p.display_name,
            description: p.specialty ?? undefined,
          }))}
          onChange={(e) => {
            const p = providers.find((x) => x.id === e.detail.selectedOption.value);
            setProvider(p ?? null);
            setSlots(null);
          }}
          placeholder={office ? "Select a provider" : "Pick an office first"}
        />
      </FormField>

      <FormField label="Appointment type">
        <Select
          disabled={disabled}
          selectedOption={
            apptType
              ? {
                  value: apptType.id,
                  label: `${apptType.name} (${apptType.duration_min} min)`,
                }
              : null
          }
          options={types.map((t) => ({
            value: t.id,
            label: `${t.name} (${t.duration_min} min)`,
            description: t.description ?? undefined,
          }))}
          onChange={(e) => {
            const t = types.find((x) => x.id === e.detail.selectedOption.value);
            setApptType(t ?? null);
            setSlots(null);
          }}
          placeholder="Select a visit type"
        />
      </FormField>

      <SpaceBetween direction="horizontal" size="s">
        <FormField label="From">
          <DatePicker
            value={rangeStart}
            onChange={(e) => setRangeStart(e.detail.value)}
            disabled={disabled}
          />
        </FormField>
        <FormField label="To">
          <DatePicker
            value={rangeEnd}
            onChange={(e) => setRangeEnd(e.detail.value)}
            disabled={disabled}
          />
        </FormField>
        <Box padding={{ top: "xl" }}>
          <Button
            onClick={loadSlots}
            loading={loadingSlots}
            disabled={disabled || !office || !provider || !apptType}
          >
            Find times
          </Button>
        </Box>
      </SpaceBetween>

      {slots !== null && (
        <FormField label="Available times">
          {slots.length === 0 ? (
            <Alert type="info">No open slots in that range. Try a wider window.</Alert>
          ) : (
            <SpaceBetween direction="horizontal" size="xs">
              {slots.map((s) => (
                <Button
                  key={s.start_at}
                  disabled={disabled}
                  onClick={() => {
                    if (office && provider && apptType) {
                      onSelected({ office, provider, appointmentType: apptType, slot: s });
                    }
                  }}
                >
                  {fmtDayTime(s.start_at)}
                </Button>
              ))}
            </SpaceBetween>
          )}
        </FormField>
      )}
    </SpaceBetween>
  );
}
