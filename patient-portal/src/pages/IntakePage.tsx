import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Checkbox from "@cloudscape-design/components/checkbox";
import Container from "@cloudscape-design/components/container";
import DatePicker from "@cloudscape-design/components/date-picker";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import Textarea from "@cloudscape-design/components/textarea";
import { portalApi, IntakeForm, IntakeSubmission } from "../api/portal";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

interface Field {
  key: string;
  type: string;
  label?: string;
  required?: boolean;
  options?: (string | { value: string; label?: string })[];
}

function fieldsOf(form: IntakeForm): Field[] {
  const out: Field[] = [];
  const schema = (form.schema ?? {}) as {
    pages?: { sections?: { fields?: Field[] }[] }[];
  };
  for (const page of schema.pages ?? []) {
    for (const section of page.sections ?? []) {
      for (const field of section.fields ?? []) {
        if (field?.key) out.push(field);
      }
    }
  }
  return out;
}

function optionList(field: Field) {
  return (field.options ?? []).map((o) =>
    typeof o === "string" ? { value: o, label: o } : { value: o.value, label: o.label ?? o.value },
  );
}

export default function IntakePage() {
  const { push } = useFlash();
  const [forms, setForms] = useState<IntakeForm[]>([]);
  const [submissions, setSubmissions] = useState<IntakeSubmission[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeForm, setActiveForm] = useState<IntakeForm | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [signature, setSignature] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const [f, s] = await Promise.all([portalApi.listForms(), portalApi.listSubmissions()]);
      setForms(f);
      setSubmissions(s);
    } catch {
      push({ type: "error", content: "Could not load intake forms." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startForm(form: IntakeForm) {
    setActiveForm(form);
    setAnswers({});
    setSignature("");
    setError(null);
  }

  function setAnswer(key: string, value: unknown) {
    setAnswers((prev) => ({ ...prev, [key]: value }));
  }

  function renderField(field: Field) {
    const label = field.label ?? field.key;
    const value = answers[field.key];
    switch (field.type) {
      case "textarea":
        return (
          <FormField key={field.key} label={label}>
            <Textarea
              value={(value as string) ?? ""}
              onChange={(e) => setAnswer(field.key, e.detail.value)}
            />
          </FormField>
        );
      case "date":
        return (
          <FormField key={field.key} label={label}>
            <DatePicker
              value={(value as string) ?? ""}
              onChange={(e) => setAnswer(field.key, e.detail.value)}
              placeholder="YYYY/MM/DD"
            />
          </FormField>
        );
      case "boolean":
      case "consent-block":
        return (
          <FormField key={field.key}>
            <Checkbox
              checked={Boolean(value)}
              onChange={(e) => setAnswer(field.key, e.detail.checked)}
            >
              {label}
            </Checkbox>
          </FormField>
        );
      case "select": {
        const opts = optionList(field);
        const sel = opts.find((o) => o.value === value) ?? null;
        return (
          <FormField key={field.key} label={label}>
            <Select
              selectedOption={sel}
              placeholder="Choose one"
              options={opts}
              onChange={(e) => setAnswer(field.key, e.detail.selectedOption.value)}
            />
          </FormField>
        );
      }
      case "number":
      case "scale":
        return (
          <FormField key={field.key} label={label}>
            <Input
              type="number"
              value={value === undefined || value === null ? "" : String(value)}
              onChange={(e) => setAnswer(field.key, e.detail.value)}
            />
          </FormField>
        );
      default:
        return (
          <FormField key={field.key} label={label}>
            <Input
              value={(value as string) ?? ""}
              onChange={(e) => setAnswer(field.key, e.detail.value)}
            />
          </FormField>
        );
    }
  }

  async function submit() {
    if (!activeForm) return;
    setError(null);
    const missing = fieldsOf(activeForm).filter(
      (f) => f.required && (answers[f.key] === undefined || answers[f.key] === ""),
    );
    if (missing.length) {
      setError(`Please complete: ${missing.map((f) => f.label ?? f.key).join(", ")}.`);
      return;
    }
    setSubmitting(true);
    try {
      await portalApi.submitIntake({
        form_id: activeForm.id,
        answers,
        signature_name: signature.trim() || null,
      });
      push({ type: "success", content: `Submitted: ${activeForm.name}.` });
      setActiveForm(null);
      await reload();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err.response?.data?.detail ?? "Submission failed.");
    } finally {
      setSubmitting(false);
    }
  }

  const formNameById = (id: string) => forms.find((f) => f.id === id)?.name ?? id;

  return (
    <PageHeader
      title="Intake forms"
      description="Complete the forms your care team has requested."
      actions={<Button iconName="refresh" onClick={reload} loading={loading} />}
    >
      <SpaceBetween size="l">
        {activeForm ? (
          <Container
            header={
              <Header
                variant="h2"
                actions={
                  <Button variant="link" onClick={() => setActiveForm(null)} disabled={submitting}>
                    Cancel
                  </Button>
                }
              >
                {activeForm.name}
              </Header>
            }
          >
            <SpaceBetween size="m">
              {error && <Alert type="error">{error}</Alert>}
              {fieldsOf(activeForm).map(renderField)}
              <FormField
                label="Signature (type your full name)"
                description="Optional — signing records the date and time."
              >
                <Input value={signature} onChange={(e) => setSignature(e.detail.value)} />
              </FormField>
              <Box float="right">
                <Button variant="primary" loading={submitting} onClick={submit}>
                  Submit form
                </Button>
              </Box>
            </SpaceBetween>
          </Container>
        ) : (
          <Table
            variant="container"
            header={<Header variant="h2" counter={`(${forms.length})`}>Available forms</Header>}
            loading={loading}
            loadingText="Loading forms"
            items={forms}
            columnDefinitions={[
              { id: "name", header: "Form", cell: (r) => r.name },
              { id: "version", header: "Version", cell: (r) => `v${r.version}` },
              {
                id: "action",
                header: "",
                cell: (r) => (
                  <Button variant="inline-link" onClick={() => startForm(r)}>
                    Fill out
                  </Button>
                ),
              },
            ]}
            empty={
              <Box textAlign="center" color="inherit">
                <b>No forms to complete</b>
              </Box>
            }
          />
        )}

        <Table
          variant="container"
          header={
            <Header variant="h2" counter={`(${submissions.length})`}>
              Your submissions
            </Header>
          }
          loading={loading}
          loadingText="Loading submissions"
          items={submissions}
          columnDefinitions={[
            { id: "form", header: "Form", cell: (r) => formNameById(r.form_id) },
            { id: "version", header: "Version", cell: (r) => `v${r.form_version}` },
            {
              id: "signed",
              header: "Signed",
              cell: (r) => (r.signed_at ? new Date(r.signed_at).toLocaleDateString() : "—"),
            },
            {
              id: "when",
              header: "Submitted",
              cell: (r) => new Date(r.created_at).toLocaleString(),
            },
          ]}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No submissions yet</b>
            </Box>
          }
        />
      </SpaceBetween>
    </PageHeader>
  );
}
