import { FormEvent, useEffect, useState } from "react";
import Badge from "@cloudscape-design/components/badge";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import DatePicker from "@cloudscape-design/components/date-picker";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Pagination from "@cloudscape-design/components/pagination";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import Toggle from "@cloudscape-design/components/toggle";
import { adminApi, AuditRow, AuditSearchParams, Tenant } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

const ENTITY_OPTIONS = [
  { value: "", label: "Any entity" },
  { value: "patient", label: "patient" },
  { value: "appointment", label: "appointment" },
  { value: "intake_submission", label: "intake_submission" },
  { value: "document", label: "document" },
  { value: "insurance_policy", label: "insurance_policy" },
  { value: "user", label: "user" },
  { value: "api_key", label: "api_key" },
  { value: "webhook_subscription", label: "webhook_subscription" },
  { value: "organization", label: "organization" },
];

const PAGE_SIZE = 50;

function isoOrNull(date: string): string | undefined {
  return date ? new Date(date).toISOString() : undefined;
}

export default function AuditSearchPage() {
  const { push } = useFlash();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const [orgId, setOrgId] = useState<string>("");
  const [actorEmail, setActorEmail] = useState("");
  const [entityType, setEntityType] = useState("");
  const [entityId, setEntityId] = useState("");
  const [action, setAction] = useState("");
  const [phiOnly, setPhiOnly] = useState(false);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        setTenants(await adminApi.listTenants());
      } catch {
        /* non-fatal */
      }
    })();
  }, []);

  async function runSearch(e?: FormEvent, targetPage = 1) {
    if (e) e.preventDefault();
    setLoading(true);
    try {
      const params: AuditSearchParams = {
        org_id: orgId || undefined,
        actor_email: actorEmail || undefined,
        entity_type: entityType || undefined,
        entity_id: entityId || undefined,
        action: action || undefined,
        phi_only: phiOnly || undefined,
        from_ts: isoOrNull(fromDate),
        to_ts: isoOrNull(toDate),
        page: targetPage,
        page_size: PAGE_SIZE,
      };
      const res = await adminApi.searchAudit(params);
      setRows(res.items);
      setTotal(res.total);
      setPage(targetPage);
    } catch {
      push({ type: "error", content: "Audit search failed" });
    } finally {
      setLoading(false);
    }
  }

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const tenantName = (id: string) => tenants.find((t) => t.id === id)?.name ?? id;

  return (
    <PageHeader
      title="Audit search"
      description="Cross-tenant PHI access and administrative actions. Every row is immutable."
    >
      <SpaceBetween size="l">
        <form onSubmit={(e) => runSearch(e, 1)}>
          <Form
            actions={
              <SpaceBetween direction="horizontal" size="xs">
                <Button variant="primary" formAction="submit" loading={loading}>
                  Search
                </Button>
              </SpaceBetween>
            }
            header={<Header variant="h2">Filters</Header>}
          >
            <SpaceBetween size="m">
              <SpaceBetween direction="horizontal" size="s">
                <FormField label="Tenant">
                  <Select
                    selectedOption={
                      orgId
                        ? { value: orgId, label: tenantName(orgId) }
                        : { value: "", label: "All tenants" }
                    }
                    options={[
                      { value: "", label: "All tenants" },
                      ...tenants.map((t) => ({ value: t.id, label: t.name })),
                    ]}
                    onChange={(e) => setOrgId(e.detail.selectedOption.value ?? "")}
                  />
                </FormField>
                <FormField label="Entity type">
                  <Select
                    selectedOption={ENTITY_OPTIONS.find((o) => o.value === entityType) ?? ENTITY_OPTIONS[0]}
                    options={ENTITY_OPTIONS}
                    onChange={(e) => setEntityType(e.detail.selectedOption.value ?? "")}
                  />
                </FormField>
                <FormField label="Actor email">
                  <Input value={actorEmail} onChange={(e) => setActorEmail(e.detail.value)} />
                </FormField>
                <FormField label="Entity ID">
                  <Input value={entityId} onChange={(e) => setEntityId(e.detail.value)} />
                </FormField>
                <FormField label="Action">
                  <Input
                    value={action}
                    onChange={(e) => setAction(e.detail.value)}
                    placeholder="read, create, update, delete"
                  />
                </FormField>
              </SpaceBetween>
              <SpaceBetween direction="horizontal" size="s">
                <FormField label="From">
                  <DatePicker value={fromDate} onChange={(e) => setFromDate(e.detail.value)} />
                </FormField>
                <FormField label="To">
                  <DatePicker value={toDate} onChange={(e) => setToDate(e.detail.value)} />
                </FormField>
                <FormField label="PHI accessed only">
                  <Toggle checked={phiOnly} onChange={(e) => setPhiOnly(e.detail.checked)}>
                    {phiOnly ? "On" : "Off"}
                  </Toggle>
                </FormField>
              </SpaceBetween>
            </SpaceBetween>
          </Form>
        </form>

        <Table
          variant="container"
          header={<Header counter={`(${total})`}>Results</Header>}
          loading={loading}
          loadingText="Searching"
          items={rows}
          trackBy="id"
          columnDefinitions={[
            {
              id: "ts",
              header: "Time",
              cell: (r) => new Date(r.created_at).toLocaleString(),
            },
            { id: "tenant", header: "Tenant", cell: (r) => tenantName(r.org_id) },
            { id: "actor", header: "Actor", cell: (r) => r.actor_email ?? r.actor_type },
            { id: "entity", header: "Entity", cell: (r) => `${r.entity_type} ${r.entity_id ?? ""}` },
            { id: "action", header: "Action", cell: (r) => r.action },
            {
              id: "phi",
              header: "PHI",
              cell: (r) => (r.phi_accessed ? <Badge color="red">PHI</Badge> : <Badge color="grey">no</Badge>),
            },
            { id: "ip", header: "IP", cell: (r) => r.ip ?? "—" },
            {
              id: "detail",
              header: "Detail",
              cell: (r) =>
                r.changes ? (
                  <ExpandableSection headerText="View">
                    <pre style={{ margin: 0, fontSize: 12, whiteSpace: "pre-wrap" }}>
                      {JSON.stringify(r.changes, null, 2)}
                    </pre>
                  </ExpandableSection>
                ) : (
                  "—"
                ),
            },
          ]}
          pagination={
            <Pagination
              currentPageIndex={page}
              pagesCount={pageCount}
              onChange={(e) => void runSearch(undefined, e.detail.currentPageIndex)}
            />
          }
          empty={
            <Box textAlign="center" color="inherit">
              <b>No results</b>
              <Box variant="p">Run a search to see cross-tenant audit rows.</Box>
            </Box>
          }
        />
      </SpaceBetween>
    </PageHeader>
  );
}
