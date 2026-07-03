import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Tabs from "@cloudscape-design/components/tabs";
import Container from "@cloudscape-design/components/container";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Header from "@cloudscape-design/components/header";
import Box from "@cloudscape-design/components/box";
import Spinner from "@cloudscape-design/components/spinner";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import PageHeader from "../components/layout/PageHeader";
import { Appointment, appointmentsApi, Patient, patientsApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <Box variant="awsui-key-label">{label}</Box>
      <div>{value ?? "—"}</div>
    </div>
  );
}

function formatAddress(address: Patient["address"]): string | null {
  if (!address) return null;
  const parts = [
    address.line1,
    address.line2,
    [address.city, address.state].filter(Boolean).join(", "),
    address.postal_code,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

export default function PatientDetailPage() {
  const { id = "" } = useParams();
  const nav = useNavigate();
  const { push } = useFlash();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [appts, setAppts] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      patientsApi.get(id),
      appointmentsApi.list({}).then((r) => (r.items ?? []).filter((a) => a.patient_id === id)),
    ])
      .then(([p, a]) => { setPatient(p); setAppts(a); })
      .catch(() => push({ type: "error", content: "Failed to load patient" }))
      .finally(() => setLoading(false));
  }, [id, push]);

  if (loading) {
    return <PageHeader title="Patient"><Box textAlign="center" padding="xxl"><Spinner size="large" /></Box></PageHeader>;
  }
  if (!patient) {
    return <PageHeader title="Patient not found"><Button onClick={() => nav("/patients")}>Back to patients</Button></PageHeader>;
  }

  return (
    <PageHeader
      title={`${patient.first_name} ${patient.last_name}`}
      description={patient.mrn ? `MRN ${patient.mrn}` : "No MRN assigned"}
      actions={
        <SpaceBetween direction="horizontal" size="xs">
          <Button onClick={() => nav("/patients")}>Back</Button>
          <Button variant="primary" onClick={() => nav(`/appointments?patient=${patient.id}`)}>Book appointment</Button>
        </SpaceBetween>
      }
    >
      <Tabs
        tabs={[
          {
            label: "Overview",
            id: "overview",
            content: (
              <Container header={<Header variant="h2">Demographics</Header>}>
                <ColumnLayout columns={2} variant="text-grid">
                  <Field label="MRN" value={patient.mrn} />
                  <Field label="First name" value={patient.first_name} />
                  <Field label="Middle name" value={patient.middle_name} />
                  <Field label="Last name" value={patient.last_name} />
                  <Field label="Date of birth" value={patient.dob} />
                  <Field label="Sex" value={patient.sex} />
                  <Field label="Email" value={patient.email} />
                  <Field label="Phone" value={patient.phone} />
                  <Field label="Address" value={formatAddress(patient.address)} />
                  <Field label="SMS opted in" value={patient.sms_opt_in_at ? "Yes" : "No"} />
                </ColumnLayout>
              </Container>
            ),
          },
          {
            label: `Appointments (${appts.length})`,
            id: "appts",
            content: (
              <Table
                items={appts}
                columnDefinitions={[
                  { id: "start", header: "Start", cell: (a) => new Date(a.start_at).toLocaleString() },
                  { id: "end", header: "End", cell: (a) => new Date(a.end_at).toLocaleString() },
                  { id: "status", header: "Status", cell: (a) => a.status },
                  { id: "source", header: "Source", cell: (a) => a.source },
                ]}
                empty={<Box textAlign="center" padding="l">No appointments</Box>}
              />
            ),
          },
          { label: "Intake", id: "intake", content: <Container><Box padding="l">Intake submissions render here.</Box></Container> },
          { label: "Insurance", id: "insurance", content: <Container><Box padding="l">Insurance policies render here.</Box></Container> },
          { label: "Documents", id: "docs", content: <Container><Box padding="l">Documents render here.</Box></Container> },
        ]}
      />
    </PageHeader>
  );
}
