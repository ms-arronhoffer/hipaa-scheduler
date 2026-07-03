import { apiClient } from "./client";
export const adminApi = {
    // Tenants
    listTenants: () => apiClient.get("/admin/tenants").then((r) => {
        const d = r.data;
        return d.items ?? r.data;
    }),
    getTenant: (id) => apiClient.get(`/admin/tenants/${id}`).then((r) => r.data),
    createTenant: (data) => apiClient.post("/admin/tenants", data).then((r) => r.data),
    updateTenant: (id, data) => apiClient.patch(`/admin/tenants/${id}`, data).then((r) => r.data),
    suspendTenant: (id) => apiClient.post(`/admin/tenants/${id}/suspend`).then((r) => r.data),
    activateTenant: (id) => apiClient.post(`/admin/tenants/${id}/activate`).then((r) => r.data),
    // Plans
    listPlans: () => apiClient.get("/admin/plans").then((r) => {
        const d = r.data;
        return d.items ?? r.data;
    }),
    overrideSeats: (org_id, seats) => apiClient
        .post(`/admin/seats/override`, { org_id, seats })
        .then((r) => r.data),
    overridePlan: (org_id, plan_id) => apiClient
        .post(`/admin/plans/override`, { org_id, plan_id })
        .then((r) => r.data),
    // Audit search (cross-tenant)
    searchAudit: (params) => apiClient
        .get("/admin/audit-search", { params })
        .then((r) => r.data),
    // Impersonation
    impersonate: (org_id, user_id, reason) => apiClient
        .post("/admin/impersonate", { org_id, user_id, reason })
        .then((r) => r.data),
    endImpersonation: () => apiClient.post("/admin/impersonate/end").then((r) => r.data),
    // BAA
    listBaa: () => apiClient.get("/admin/baa").then((r) => {
        const d = r.data;
        return d.items ?? r.data;
    }),
    updateBaa: (org_id, data) => apiClient.patch(`/admin/baa/${org_id}`, data).then((r) => r.data),
    // System health
    systemHealth: () => apiClient.get("/admin/system/health").then((r) => r.data),
};
