import { apiClient } from "./client";

// Thin wrappers around backend routers. Each domain gets its own file so the
// endpoints stay discoverable next to the pages that use them.

// Patients
export interface Patient {
  id: string;
  mrn: string | null;
  first_name: string;
  last_name: string;
  dob: string | null;
  email: string | null;
  phone: string | null;
  sms_opt_in_at: string | null;
  created_at: string;
}
export const patientsApi = {
  list: (params: { q?: string; limit?: number; offset?: number } = {}) =>
    apiClient.get<{ items: Patient[]; total: number }>("/patients", { params }).then((r) => r.data),
  get: (id: string) => apiClient.get<Patient>(`/patients/${id}`).then((r) => r.data),
  create: (body: Partial<Patient>) => apiClient.post<Patient>("/patients", body).then((r) => r.data),
  update: (id: string, body: Partial<Patient>) =>
    apiClient.patch<Patient>(`/patients/${id}`, body).then((r) => r.data),
};

// Appointments
export interface Appointment {
  id: string;
  patient_id: string;
  provider_id: string;
  office_id: string;
  appointment_type_id: string;
  start_at: string;
  end_at: string;
  status: string;
  source: string;
}
export const appointmentsApi = {
  list: (params: {
    from_ts?: string;
    to_ts?: string;
    provider_id?: string;
    office_id?: string;
    status?: string;
  } = {}) =>
    apiClient.get<{ items: Appointment[]; total: number }>("/appointments", { params }).then((r) => r.data),
  get: (id: string) => apiClient.get<Appointment>(`/appointments/${id}`).then((r) => r.data),
  create: (body: Partial<Appointment>) =>
    apiClient.post<Appointment>("/appointments", body).then((r) => r.data),
  cancel: (id: string, reason: string) =>
    apiClient.post(`/appointments/${id}/cancel`, { reason }).then((r) => r.data),
};

// Offices / Providers / AppointmentTypes / Users / Waitlist / Reports / etc.
export const officesApi = {
  list: () => apiClient.get("/offices").then((r) => r.data),
  create: (body: unknown) => apiClient.post("/offices", body).then((r) => r.data),
  update: (id: string, body: unknown) => apiClient.patch(`/offices/${id}`, body).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/offices/${id}`),
};

export const providersApi = {
  list: () => apiClient.get("/providers").then((r) => r.data),
};

export const appointmentTypesApi = {
  list: () => apiClient.get("/appointment-types").then((r) => r.data),
  create: (body: unknown) => apiClient.post("/appointment-types", body).then((r) => r.data),
  update: (id: string, body: unknown) =>
    apiClient.patch(`/appointment-types/${id}`, body).then((r) => r.data),
};

export const usersApi = {
  list: () => apiClient.get("/users").then((r) => r.data),
  create: (body: unknown) => apiClient.post("/users", body).then((r) => r.data),
  update: (id: string, body: unknown) => apiClient.patch(`/users/${id}`, body).then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/users/${id}`),
};

export const waitlistApi = {
  list: () => apiClient.get("/waitlist").then((r) => r.data),
};

export const intakeFormsApi = {
  list: () => apiClient.get("/intake-forms").then((r) => r.data),
  get: (id: string) => apiClient.get(`/intake-forms/${id}`).then((r) => r.data),
  create: (body: unknown) => apiClient.post("/intake-forms", body).then((r) => r.data),
  update: (id: string, body: unknown) =>
    apiClient.patch(`/intake-forms/${id}`, body).then((r) => r.data),
};

export const apiKeysApi = {
  list: () => apiClient.get("/api-keys").then((r) => r.data),
  // Plaintext key is returned once on create — surface it in a modal.
  create: (body: { name: string; scopes: string[] }) =>
    apiClient.post<{ id: string; plaintext: string; prefix: string }>("/api-keys", body).then((r) => r.data),
  revoke: (id: string) => apiClient.post(`/api-keys/${id}/revoke`),
  delete: (id: string) => apiClient.delete(`/api-keys/${id}`),
};

export const webhooksApi = {
  list: () => apiClient.get("/webhooks").then((r) => r.data),
  create: (body: { url: string; events: string[] }) =>
    apiClient.post("/webhooks", body).then((r) => r.data),
  update: (id: string, body: unknown) => apiClient.patch(`/webhooks/${id}`, body).then((r) => r.data),
  rotate: (id: string) =>
    apiClient.post<{ secret: string }>(`/webhooks/${id}/rotate`).then((r) => r.data),
  deliveries: (id: string) => apiClient.get(`/webhooks/${id}/deliveries`).then((r) => r.data),
  retry: (id: string, delivery_id: string) =>
    apiClient.post(`/webhooks/${id}/deliveries/${delivery_id}/retry`),
};

export const calendarConnectionsApi = {
  list: () => apiClient.get("/calendar-connections").then((r) => r.data),
  delete: (id: string) => apiClient.delete(`/calendar-connections/${id}`),
};

export const activityLogApi = {
  list: (params: { entity_type?: string; phi_only?: boolean; limit?: number; offset?: number } = {}) =>
    apiClient.get<{ items: ActivityLogEntry[]; total: number }>("/activity-log", { params }).then((r) => r.data),
};

export interface ActivityLogEntry {
  id: string;
  actor_type: string;
  actor_email: string | null;
  entity_type: string;
  entity_id: string | null;
  action: string;
  phi_accessed: boolean;
  changes: Record<string, unknown>;
  ip: string | null;
  created_at: string;
}

export const organizationApi = {
  get: () => apiClient.get("/organization").then((r) => r.data),
  update: (body: unknown) => apiClient.patch("/organization", body).then((r) => r.data),
};

export const reportsApi = {
  utilization: (params: { from_ts?: string; to_ts?: string } = {}) =>
    apiClient.get("/reports/utilization", { params }).then((r) => r.data),
  noShows: (params: { from_ts?: string; to_ts?: string } = {}) =>
    apiClient.get("/reports/no-shows", { params }).then((r) => r.data),
};
