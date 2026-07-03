import { apiClient } from "./client";

// Super-admin cross-tenant surface. Endpoints live under /admin/* and require
// is_super_admin. Never call these from the staff or patient SPAs.

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  seats: number;
  seats_used: number;
  baa_signed_at: string | null;
  mfa_required: boolean;
  created_at: string;
  active: boolean;
}

export interface TenantCreate {
  name: string;
  slug: string;
  plan: string;
  seats: number;
  admin_email: string;
  admin_first_name?: string;
  admin_last_name?: string;
}

export interface Plan {
  id: string;
  name: string;
  seat_limit: number;
  features: Record<string, boolean>;
  monthly_price_cents: number;
}

export interface AuditRow {
  id: string;
  org_id: string;
  org_name?: string;
  actor_type: string;
  actor_id: string | null;
  actor_email: string | null;
  entity_type: string;
  entity_id: string | null;
  action: string;
  phi_accessed: boolean;
  ip: string | null;
  user_agent: string | null;
  changes: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditSearchParams {
  org_id?: string;
  actor_email?: string;
  entity_type?: string;
  entity_id?: string;
  action?: string;
  phi_only?: boolean;
  from_ts?: string;
  to_ts?: string;
  page?: number;
  page_size?: number;
}

export interface ImpersonationResponse {
  access_token: string;
  expires_at: string;
  target_org_id: string;
  target_user_id: string;
}

export interface SystemHealth {
  database: { ok: boolean; latency_ms: number };
  scheduler: { ok: boolean; jobs_registered: number; next_run_at: string | null };
  webhook_queue: { pending: number; failed_last_24h: number };
  storage: { ok: boolean };
  build: { version: string; commit: string; started_at: string };
}

export interface BaaTenant {
  org_id: string;
  org_name: string;
  baa_signed_at: string | null;
  baa_expires_at: string | null;
  baa_document_key: string | null;
  contact_email: string | null;
}

export const adminApi = {
  // Tenants
  listTenants: () =>
    apiClient.get<Tenant[] | { items: Tenant[] }>("/admin/tenants").then((r) => {
      const d = r.data as { items?: Tenant[] };
      return d.items ?? (r.data as Tenant[]);
    }),
  getTenant: (id: string) =>
    apiClient.get<Tenant>(`/admin/tenants/${id}`).then((r) => r.data),
  createTenant: (data: TenantCreate) =>
    apiClient.post<Tenant>("/admin/tenants", data).then((r) => r.data),
  updateTenant: (id: string, data: Partial<Tenant>) =>
    apiClient.patch<Tenant>(`/admin/tenants/${id}`, data).then((r) => r.data),
  suspendTenant: (id: string) =>
    apiClient.post<Tenant>(`/admin/tenants/${id}/suspend`).then((r) => r.data),
  activateTenant: (id: string) =>
    apiClient.post<Tenant>(`/admin/tenants/${id}/activate`).then((r) => r.data),

  // Plans
  listPlans: () =>
    apiClient.get<Plan[] | { items: Plan[] }>("/admin/plans").then((r) => {
      const d = r.data as { items?: Plan[] };
      return d.items ?? (r.data as Plan[]);
    }),
  overrideSeats: (org_id: string, seats: number) =>
    apiClient
      .post<Tenant>(`/admin/seats/override`, { org_id, seats })
      .then((r) => r.data),
  overridePlan: (org_id: string, plan_id: string) =>
    apiClient
      .post<Tenant>(`/admin/plans/override`, { org_id, plan_id })
      .then((r) => r.data),

  // Audit search (cross-tenant). Backend route is /admin/audit/search and
  // paginates with limit/offset; the UI thinks in page/page_size, so translate.
  searchAudit: (params: AuditSearchParams) => {
    const { page, page_size, ...rest } = params;
    const size = page_size ?? 50;
    const query = {
      ...rest,
      limit: size,
      offset: page && page > 1 ? (page - 1) * size : 0,
    };
    return apiClient
      .get<{ items: AuditRow[]; total: number }>("/admin/audit/search", { params: query })
      .then((r) => r.data);
  },

  // Impersonation
  impersonate: (org_id: string, user_id?: string, reason?: string) =>
    apiClient
      .post<ImpersonationResponse>("/admin/impersonate", { org_id, user_id, reason })
      .then((r) => r.data),
  endImpersonation: () =>
    apiClient.post("/admin/impersonate/end").then((r) => r.data),

  // BAA
  listBaa: () =>
    apiClient.get<BaaTenant[] | { items: BaaTenant[] }>("/admin/baa").then((r) => {
      const d = r.data as { items?: BaaTenant[] };
      return d.items ?? (r.data as BaaTenant[]);
    }),
  updateBaa: (
    org_id: string,
    data: { baa_signed_at?: string | null; baa_expires_at?: string | null; baa_document_key?: string | null },
  ) => apiClient.patch<BaaTenant>(`/admin/baa/${org_id}`, data).then((r) => r.data),

  // System health
  systemHealth: () =>
    apiClient.get<SystemHealth>("/admin/system/health").then((r) => r.data),
};
