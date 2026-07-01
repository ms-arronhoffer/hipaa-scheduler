import { FormEvent, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Checkbox from "@cloudscape-design/components/checkbox";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import DatePicker from "@cloudscape-design/components/date-picker";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Textarea from "@cloudscape-design/components/textarea";
import { publicApi } from "../api/publicBooking";
import PageHeader from "../components/layout/PageHeader";
import SlotPicker, { Selection } from "../components/SlotPicker";

const HIPAA_VERSION = "v1-2026-01";

export default function GuestBookPage() {
  const { slug = "" } = useParams();
  const nav = useNavigate();

  const [sel, setSel] = useState<Selection | null>(null);
  const [first, setFirst] = useState("");
  const [last, setLast] = useState("");
  const [dob, setDob] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [hipaa, setHipaa] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!sel) return;
    if (!hipaa) {
      setErr("You must accept the notice of privacy practices to continue.");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const res = await publicApi.bookAsGuest({
        org_slug: slug,
        office_id: sel.office.id,
        provider_id: sel.provider.id,
        appointment_type_id: sel.appointmentType.id,
        start_at: sel.slot.start_at,
        patient: {
          first_name: first,
          last_name: last,
          dob,
          email,
          phone: phone || null,
        },
        accept_hipaa_version: HIPAA_VERSION,
        notes: notes || null,
      });
      const params = new URLSearchParams();
      if (res.claim_token) params.set("claim", res.claim_token);
      nav(`/o/${slug}/booked?${params.toString()}`);
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
    <PageHeader
      title="Book as a guest"
      description="No account needed. You'll be able to claim your account after booking."
    >
      <form onSubmit={submit}>
        <Form
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => nav(`/o/${slug}`)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={saving}
                disabled={!sel || !first || !last || !dob || !email || !hipaa}
                onClick={() => void submit(new Event("submit") as unknown as FormEvent)}
              >
                Confirm booking
              </Button>
            </SpaceBetween>
          }
        >
          <SpaceBetween size="l">
            {err && <Alert type="error">{err}</Alert>}

            <Container header={<Header variant="h2">1. Pick a time</Header>}>
              {!sel ? (
                <SlotPicker orgSlug={slug} onSelected={setSel} disabled={saving} />
              ) : (
                <SpaceBetween size="s">
                  <Box>
                    <b>{sel.appointmentType.name}</b> with {sel.provider.display_name} at{" "}
                    {sel.office.name}
                  </Box>
                  <Box>{new Date(sel.slot.start_at).toLocaleString()}</Box>
                  <Button onClick={() => setSel(null)} disabled={saving}>
                    Change time
                  </Button>
                </SpaceBetween>
              )}
            </Container>

            <Container header={<Header variant="h2">2. About you</Header>}>
              <SpaceBetween size="m">
                <ColumnLayout columns={2}>
                  <FormField label="First name">
                    <Input value={first} onChange={(e) => setFirst(e.detail.value)} />
                  </FormField>
                  <FormField label="Last name">
                    <Input value={last} onChange={(e) => setLast(e.detail.value)} />
                  </FormField>
                  <FormField label="Date of birth">
                    <DatePicker value={dob} onChange={(e) => setDob(e.detail.value)} />
                  </FormField>
                  <FormField label="Email">
                    <Input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.detail.value)}
                    />
                  </FormField>
                  <FormField label="Phone (optional)">
                    <Input value={phone} onChange={(e) => setPhone(e.detail.value)} />
                  </FormField>
                </ColumnLayout>
                <FormField label="Notes (optional)">
                  <Textarea value={notes} onChange={(e) => setNotes(e.detail.value)} />
                </FormField>
              </SpaceBetween>
            </Container>

            <Container header={<Header variant="h2">3. Privacy</Header>}>
              <Checkbox checked={hipaa} onChange={(e) => setHipaa(e.detail.checked)}>
                I acknowledge I have received the Notice of Privacy Practices
                ({HIPAA_VERSION}).
              </Checkbox>
            </Container>
          </SpaceBetween>
        </Form>
      </form>
    </PageHeader>
  );
}
