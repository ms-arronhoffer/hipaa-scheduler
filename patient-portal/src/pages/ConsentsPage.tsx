import { useEffect, useMemo, useState } from "react";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Cards from "@cloudscape-design/components/cards";
import Container from "@cloudscape-design/components/container";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import { portalApi, Consent, PatientDocument } from "../api/portal";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

/**
 * Consent documents a patient can review and sign in the portal. The body text
 * lives client-side; we hash it (SHA-256) so the backend records exactly which
 * wording was agreed to, matching the staff-side consent records.
 */
interface ConsentTemplate {
  kind: string;
  label: string;
  version: string;
  body: string;
}

const CONSENT_TEMPLATES: ConsentTemplate[] = [
  {
    kind: "hipaa_privacy",
    label: "HIPAA Notice of Privacy Practices",
    version: "2024-01",
    body:
      "I acknowledge that I have received and reviewed the Notice of Privacy " +
      "Practices describing how my protected health information may be used and disclosed.",
  },
  {
    kind: "telehealth",
    label: "Telehealth Consent",
    version: "2024-01",
    body:
      "I consent to receive care via telehealth and understand the benefits, " +
      "risks, and limitations of remote visits.",
  },
  {
    kind: "sms",
    label: "SMS / Text Message Consent",
    version: "2024-01",
    body:
      "I consent to receive appointment reminders and related messages by SMS. " +
      "Message and data rates may apply; I can opt out at any time.",
  },
  {
    kind: "financial",
    label: "Financial Responsibility",
    version: "2024-01",
    body:
      "I understand I am financially responsible for charges not covered by my " +
      "insurance and agree to the practice's payment and cancellation policies.",
  },
];

async function sha256Hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

export default function ConsentsPage() {
  const { push } = useFlash();
  const [consents, setConsents] = useState<Consent[]>([]);
  const [documents, setDocuments] = useState<PatientDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [signerName, setSignerName] = useState("");
  const [selectedKind, setSelectedKind] = useState<string>(CONSENT_TEMPLATES[0].kind);
  const [signing, setSigning] = useState(false);

  const signedKinds = useMemo(
    () => new Set(consents.map((c) => `${c.kind}:${c.document_version}`)),
    [consents],
  );

  async function reload() {
    setLoading(true);
    try {
      const [c, d] = await Promise.all([portalApi.listConsents(), portalApi.listDocuments()]);
      setConsents(c);
      setDocuments(d);
    } catch {
      push({ type: "error", content: "Could not load your consents and documents." });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const template = CONSENT_TEMPLATES.find((t) => t.kind === selectedKind)!;
  const alreadySigned = signedKinds.has(`${template.kind}:${template.version}`);

  async function doSign() {
    if (!signerName.trim()) {
      push({ type: "error", content: "Please type your full name to sign." });
      return;
    }
    setSigning(true);
    try {
      const body_hash = await sha256Hex(template.body);
      await portalApi.signConsent({
        kind: template.kind,
        document_version: template.version,
        body_hash,
        signer_name: signerName.trim(),
      });
      push({ type: "success", content: `Signed: ${template.label}.` });
      setSignerName("");
      await reload();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      push({ type: "error", content: err.response?.data?.detail ?? "Could not record consent." });
    } finally {
      setSigning(false);
    }
  }

  return (
    <PageHeader
      title="Consents & documents"
      description="Review and sign consent forms, and see documents on file."
      actions={<Button iconName="refresh" onClick={reload} loading={loading} />}
    >
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Sign a consent</Header>}>
          <SpaceBetween size="m">
            <FormField label="Consent form">
              <Select
                selectedOption={{ value: template.kind, label: template.label }}
                onChange={(e) => setSelectedKind(e.detail.selectedOption.value as string)}
                options={CONSENT_TEMPLATES.map((t) => ({ value: t.kind, label: t.label }))}
              />
            </FormField>
            <Box variant="p" color="text-body-secondary">
              {template.body}
            </Box>
            {alreadySigned ? (
              <StatusIndicator type="success">
                You have already signed this version.
              </StatusIndicator>
            ) : (
              <FormField label="Type your full name to sign" stretch>
                <SpaceBetween size="xs" direction="horizontal">
                  <Input
                    value={signerName}
                    onChange={(e) => setSignerName(e.detail.value)}
                    placeholder="Full name"
                  />
                  <Button variant="primary" loading={signing} onClick={doSign}>
                    Sign consent
                  </Button>
                </SpaceBetween>
              </FormField>
            )}
          </SpaceBetween>
        </Container>

        <Table
          variant="container"
          header={<Header variant="h2" counter={`(${consents.length})`}>Signed consents</Header>}
          loading={loading}
          loadingText="Loading consents"
          items={consents}
          columnDefinitions={[
            { id: "kind", header: "Form", cell: (r) => r.kind },
            { id: "version", header: "Version", cell: (r) => r.document_version },
            { id: "signer", header: "Signed by", cell: (r) => r.signer_name },
            { id: "when", header: "Signed at", cell: (r) => new Date(r.signed_at).toLocaleString() },
          ]}
          empty={
            <Box textAlign="center" color="inherit">
              <b>No consents on file yet</b>
            </Box>
          }
        />

        <div>
          <Header variant="h2" counter={`(${documents.length})`}>
            Documents on file
          </Header>
          <Cards
            items={documents}
            loading={loading}
            loadingText="Loading documents"
            cardDefinition={{
              header: (d) => d.filename,
              sections: [
                { id: "kind", header: "Type", content: (d) => d.kind },
                {
                  id: "size",
                  header: "Size",
                  content: (d) => `${Math.max(1, Math.round(d.size_bytes / 1024))} KB`,
                },
                {
                  id: "added",
                  header: "Added",
                  content: (d) => new Date(d.created_at).toLocaleDateString(),
                },
              ],
            }}
            cardsPerRow={[{ cards: 1 }, { minWidth: 500, cards: 2 }]}
            empty={
              <Box textAlign="center" color="inherit">
                <b>No documents yet</b>
                <Box variant="p" color="inherit">
                  Documents uploaded by your care team will appear here.
                </Box>
              </Box>
            }
          />
        </div>
      </SpaceBetween>
    </PageHeader>
  );
}
