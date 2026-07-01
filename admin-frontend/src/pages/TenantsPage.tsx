import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Modal from "@cloudscape-design/components/modal";
import Pagination from "@cloudscape-design/components/pagination";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import TextFilter from "@cloudscape-design/components/text-filter";
import { adminApi, Plan, Tenant, TenantCreate } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

const PAGE_SIZE = 25;
const EMPTY_CREATE: TenantCreate = {
  name: "",
  slug: "",
  plan: "starter",
  seats: 5,
  admin_email: "",
};

export default function TenantsPage() {
  const nav = useNavigate();
  const { push } = useFlash();
  const [rows, setRows] = useState<Tenant[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [create, setCreate] = useState<TenantCreate>(EMPTY_CREATE);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const [t, p] = await Promise.all([adminApi.listTenants(), adminApi.listPlans()]);
      setRows(t);
      setPlans(p);
    } catch {
      push({ type: "error", content: "Failed to load tenants" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filtered = useMemo(() => {
    if (!filter) return rows;
    const f = filter.toLowerCase();
    return rows.filter(
      (r) =>
        r.name.toLowerCase().includes(f) ||
        r.slug.toLowerCase().includes(f) ||
        r.plan.toLowerCase().includes(f),
    );
  }, [rows, filter]);

  const pageRows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));

  async function submitCreate(e: FormEvent) {
    e.preventDefault();
    setCreateError(null);
    if (!create.name || !create.slug || !create.admin_email) {
      setCreateError("Name, slug, and admin email are required");
      return;
    }
    setCreating(true);
    try {
      const t = await adminApi.createTenant(create);
      push({ type: "success", content: `Tenant ${t.name} created.` });
      setShowCreate(false);
      setCreate(EMPTY_CREATE);
      await reload();
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setCreateError(err.response?.data?.detail ?? "Failed to create tenant");
    } finally {
      setCreating(false);
    }
  }

  return (
    <PageHeader
      title="Tenants"
      description="Every practice provisioned on this deployment."
      actions={
        <SpaceBetween direction="horizontal" size="xs">
          <Button iconName="refresh" onClick={reload} loading={loading} />
          <Button variant="primary" onClick={() => setShowCreate(true)}>
            New tenant
          </Button>
        </SpaceBetween>
      }
    >
      <Table
        variant="container"
        loading={loading}
        loadingText="Loading tenants"
        items={pageRows}
        selectionType="single"
        onRowClick={(e) => nav(`/tenants/${e.detail.item.id}`)}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (t) => t.name, sortingField: "name" },
          { id: "slug", header: "Slug", cell: (t) => <code>{t.slug}</code> },
          { id: "plan", header: "Plan", cell: (t) => t.plan },
          {
            id: "seats",
            header: "Seats",
            cell: (t) => `${t.seats_used} / ${t.seats}`,
          },
          {
            id: "baa",
            header: "BAA",
            cell: (t) =>
              t.baa_signed_at ? (
                <StatusIndicator type="success">Signed</StatusIndicator>
              ) : (
                <StatusIndicator type="warning">Missing</StatusIndicator>
              ),
          },
          {
            id: "mfa",
            header: "MFA",
            cell: (t) =>
              t.mfa_required ? (
                <StatusIndicator type="success">Required</StatusIndicator>
              ) : (
                <StatusIndicator type="stopped">Optional</StatusIndicator>
              ),
          },
          {
            id: "status",
            header: "Status",
            cell: (t) =>
              t.active ? (
                <StatusIndicator type="success">Active</StatusIndicator>
              ) : (
                <StatusIndicator type="error">Suspended</StatusIndicator>
              ),
          },
          { id: "created", header: "Created", cell: (t) => new Date(t.created_at).toLocaleDateString() },
        ]}
        filter={
          <TextFilter
            filteringText={filter}
            filteringPlaceholder="Filter by name, slug, or plan"
            onChange={(e) => {
              setFilter(e.detail.filteringText);
              setPage(1);
            }}
            countText={`${filtered.length} matches`}
          />
        }
        pagination={
          <Pagination
            currentPageIndex={page}
            pagesCount={pageCount}
            onChange={(e) => setPage(e.detail.currentPageIndex)}
          />
        }
        empty={
          <Box textAlign="center" color="inherit">
            <b>No tenants yet</b>
            <Box variant="p" color="inherit">
              Provision the first practice to get started.
            </Box>
          </Box>
        }
      />

      <Modal
        visible={showCreate}
        onDismiss={() => setShowCreate(false)}
        header="New tenant"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button variant="primary" loading={creating} onClick={() => void submitCreate(new Event("submit") as unknown as FormEvent)}>
                Create
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <form onSubmit={submitCreate}>
          <Form>
            <SpaceBetween size="m">
              {createError && <Alert type="error">{createError}</Alert>}
              <FormField label="Practice name">
                <Input value={create.name} onChange={(e) => setCreate({ ...create, name: e.detail.value })} />
              </FormField>
              <FormField
                label="Slug"
                description="URL-safe identifier, e.g. acme-dental"
              >
                <Input
                  value={create.slug}
                  onChange={(e) => setCreate({ ...create, slug: e.detail.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })}
                />
              </FormField>
              <FormField label="Plan">
                <Select
                  selectedOption={{ value: create.plan, label: create.plan }}
                  options={
                    plans.length
                      ? plans.map((p) => ({ value: p.name, label: p.name }))
                      : [
                          { value: "starter", label: "starter" },
                          { value: "growth", label: "growth" },
                          { value: "enterprise", label: "enterprise" },
                        ]
                  }
                  onChange={(e) =>
                    setCreate({ ...create, plan: e.detail.selectedOption.value ?? "starter" })
                  }
                />
              </FormField>
              <FormField label="Seats">
                <Input
                  type="number"
                  value={String(create.seats)}
                  onChange={(e) => setCreate({ ...create, seats: Number(e.detail.value) || 0 })}
                />
              </FormField>
              <FormField label="Admin email" description="Initial practice_admin invited to the tenant.">
                <Input
                  type="email"
                  value={create.admin_email}
                  onChange={(e) => setCreate({ ...create, admin_email: e.detail.value })}
                />
              </FormField>
              <FormField label="Admin first name">
                <Input
                  value={create.admin_first_name ?? ""}
                  onChange={(e) => setCreate({ ...create, admin_first_name: e.detail.value })}
                />
              </FormField>
              <FormField label="Admin last name">
                <Input
                  value={create.admin_last_name ?? ""}
                  onChange={(e) => setCreate({ ...create, admin_last_name: e.detail.value })}
                />
              </FormField>
            </SpaceBetween>
          </Form>
        </form>
      </Modal>
    </PageHeader>
  );
}
