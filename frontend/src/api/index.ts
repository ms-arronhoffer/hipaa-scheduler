import { apiClient } from "./client";

// Thin wrappers around backend routers. Each domain gets its own file so the
// endpoints stay discoverable next to the pages that use them.

// Patients
export interface PatientAddress {
  line1?: string;
  line2?: string;
  city?: string;
  state?: string;
  postal_code?: string;
}
export interface Patient {
  id: string;
  mrn: string | null;
  first_name: string;
  last_name: string;
  middle_name: string | null;
  dob: string | null;
  sex: string | null;
  email: string | null;
  phone: string | null;
  address: PatientAddress;
  preferred_office_id: string | null;
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
  create: (body: {
    user_id: string;
    npi?: string | null;
    specialty?: string | null;
    default_office_id?: string | null;
    color?: string | null;
    bookable?: boolean;
  }) => apiClient.post("/providers", body).then((r) => r.data),
  update: (id: string, body: unknown) =>
    apiClient.patch(`/providers/${id}`, body).then((r) => r.data),
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

// The backend router is mounted at /intake and serializes the form body under
// the `schema` key (see IntakeFormOut). The staff UI models the same structure
// as `definition`, so translate at the boundary to keep the pages unchanged.
function toDefinition<T extends Record<string, unknown>>(row: T): T {
  if (row && "schema" in row) {
    const { schema, ...rest } = row as Record<string, unknown>;
    return { ...rest, definition: schema } as unknown as T;
  }
  return row;
}
function toSchemaBody(body: unknown): unknown {
  if (body && typeof body === "object" && "definition" in body) {
    const { definition, ...rest } = body as Record<string, unknown>;
    return { ...rest, schema: definition };
  }
  return body;
}
export const intakeFormsApi = {
  list: () => apiClient.get("/intake/forms").then((r) => r.data),
  get: (id: string) => apiClient.get(`/intake/forms/${id}`).then((r) => toDefinition(r.data)),
  create: (body: unknown) =>
    apiClient.post("/intake/forms", toSchemaBody(body)).then((r) => toDefinition(r.data)),
  update: (id: string, body: unknown) =>
    apiClient.patch(`/intake/forms/${id}`, toSchemaBody(body)).then((r) => toDefinition(r.data)),
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
    apiClient.post<{ secret: string }>(`/webhooks/${id}/rotate-secret`).then((r) => r.data),
  deliveries: (id: string) => apiClient.get(`/webhooks/${id}/deliveries`).then((r) => r.data),
  retry: (delivery_id: string) =>
    apiClient.post(`/webhooks/deliveries/${delivery_id}/retry`),
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

// The backend reports router exposes date-bounded summaries keyed by
// `range_start`/`range_end` (YYYY-MM-DD). Callers pass ISO timestamps, so
// reduce them to the date portion the endpoint expects.
function toDateRange(params: { from_ts?: string; to_ts?: string }): {
  range_start?: string;
  range_end?: string;
} {
  const out: { range_start?: string; range_end?: string } = {};
  if (params.from_ts) out.range_start = params.from_ts.slice(0, 10);
  if (params.to_ts) out.range_end = params.to_ts.slice(0, 10);
  return out;
}
export const reportsApi = {
  // NOTE: there is no `/reports/utilization` endpoint on the backend yet; this
  // call is a known gap tracked separately, not an endpoint path mismatch.
  utilization: (params: { from_ts?: string; to_ts?: string } = {}) =>
    apiClient.get("/reports/utilization", { params }).then((r) => r.data),
  noShows: (params: { from_ts?: string; to_ts?: string } = {}) =>
    apiClient.get("/reports/no-show", { params: toDateRange(params) }).then((r) => r.data),
};
