import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import FormField from "@cloudscape-design/components/form-field";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Textarea from "@cloudscape-design/components/textarea";
import { publicApi } from "../api/publicBooking";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";
import SlotPicker, { Selection } from "../components/SlotPicker";

export default function BookFlowPage() {
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const { push } = useFlash();
  const [sel, setSel] = useState<Selection | null>(null);
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function confirm() {
    if (!sel) return;
    setSaving(true);
    setErr(null);
    try {
      await publicApi.bookAsPatient({
        office_id: sel.office.id,
        provider_id: sel.provider.id,
        appointment_type_id: sel.appointmentType.id,
        start_at: sel.slot.start_at,
        notes: notes || null,
      });
      push({ type: "success", content: "Appointment booked." });
      nav(`/o/${slug}/booked`);
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string }; status?: number } };
      if (err.response?.status === 409) {
        setErr("That time was just taken. Please pick another.");
        setSel(null);
      } else {
        setErr(err.response?.data?.detail ?? "Booking failed.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageHeader title="Book an appointment" description="Pick a time that works for you.">
      <SpaceBetween size="l">
        {err && <Alert type="error">{err}</Alert>}
        {!sel ? (
          <SlotPicker orgSlug={slug} onSelected={setSel} />
        ) : (
          <Box>
            <SpaceBetween size="m">
              <Alert type="info">
                <b>{sel.appointmentType.name}</b> with {sel.provider.display_name} at{" "}
                {sel.office.name} — {new Date(sel.slot.start_at).toLocaleString()}
              </Alert>
              <FormField label="Notes (optional)" description="Anything the office should know before your visit.">
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.detail.value)}
                  placeholder="Optional"
                />
              </FormField>
              <SpaceBetween direction="horizontal" size="s">
                <Button onClick={() => setSel(null)} disabled={saving}>
                  Change time
                </Button>
                <Button variant="primary" loading={saving} onClick={confirm}>
                  Confirm booking
                </Button>
              </SpaceBetween>
            </SpaceBetween>
          </Box>
        )}
      </SpaceBetween>
    </PageHeader>
  );
}
