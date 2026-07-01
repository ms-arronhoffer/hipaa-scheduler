import { apiClient } from "./client";

export interface OrgPublic {
  id: string;
  name: string;
  slug: string;
  settings: Record<string, unknown>;
}

export interface Slot {
  start_at: string;
  end_at: string;
}

export interface Appointment {
  id: string;
  org_id: string;
  office_id: string;
  provider_id: string;
  patient_id: string;
  appointment_type_id: string;
  resource_id: string | null;
  series_id: string | null;
  start_at: string;
  end_at: string;
  duration_min: number;
  status: string;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface SlotQuery {
  org_slug: string;
  office_id: string;
  provider_id: string;
  appointment_type_id: string;
  range_start: string;
  range_end: string;
}

export interface GuestPatientDetails {
  first_name: string;
  last_name: string;
  dob: string;
  email: string;
  phone?: string | null;
}

export interface GuestBookingRequest {
  org_slug: string;
  office_id: string;
  provider_id: string;
  appointment_type_id: string;
  start_at: string;
  patient: GuestPatientDetails;
  accept_hipaa_version: string;
  notes?: string | null;
}

export interface PatientBookingRequest {
  office_id: string;
  provider_id: string;
  appointment_type_id: string;
  start_at: string;
  notes?: string | null;
}

export interface BookingResponse {
  appointment: Appointment;
  claim_token: string | null;
}

/**
 * Public/directory endpoints — no patient JWT required.
 * These read the tenant slug from the URL and drive the guest flow.
 */
export const publicApi = {
  async getOrg(slug: string): Promise<OrgPublic> {
    const r = await apiClient.get<OrgPublic>(`/pub/orgs/${slug}`);
    return r.data;
  },

  async listSlots(query: SlotQuery): Promise<Slot[]> {
    const r = await apiClient.post<{ slots: Slot[] }>("/pub/slots", query);
    return r.data.slots;
  },

  async bookAsPatient(body: PatientBookingRequest): Promise<BookingResponse> {
    const r = await apiClient.post<BookingResponse>("/pub/book/patient", body);
    return r.data;
  },

  async bookAsGuest(body: GuestBookingRequest): Promise<BookingResponse> {
    const r = await apiClient.post<BookingResponse>("/pub/book/guest", body);
    return r.data;
  },

  async myAppointments(): Promise<Appointment[]> {
    const r = await apiClient.get<Appointment[]>("/pub/me/appointments");
    return r.data;
  },

  async cancel(appointmentId: string): Promise<Appointment> {
    const r = await apiClient.post<Appointment>(`/pub/me/appointments/${appointmentId}/cancel`);
    return r.data;
  },
};

/**
 * Public directory helpers for browsing offices/providers/types for a slug.
 * These are only exposed on the public router when the org is active. If
 * later moved behind a directory router, only the URLs here need to change.
 */
export interface OfficePublic {
  id: string;
  name: string;
  timezone: string;
}

export interface ProviderPublic {
  id: string;
  display_name: string;
  specialty: string | null;
}

export interface AppointmentTypePublic {
  id: string;
  name: string;
  duration_min: number;
  description: string | null;
}

export const directoryApi = {
  async offices(slug: string): Promise<OfficePublic[]> {
    const r = await apiClient.get<OfficePublic[] | { items: OfficePublic[] }>(
      `/pub/orgs/${slug}/offices`,
    );
    const d = r.data as { items?: OfficePublic[] };
    return d.items ?? (r.data as OfficePublic[]);
  },

  async providers(slug: string, officeId: string): Promise<ProviderPublic[]> {
    const r = await apiClient.get<ProviderPublic[] | { items: ProviderPublic[] }>(
      `/pub/orgs/${slug}/offices/${officeId}/providers`,
    );
    const d = r.data as { items?: ProviderPublic[] };
    return d.items ?? (r.data as ProviderPublic[]);
  },

  async appointmentTypes(slug: string): Promise<AppointmentTypePublic[]> {
    const r = await apiClient.get<AppointmentTypePublic[] | { items: AppointmentTypePublic[] }>(
      `/pub/orgs/${slug}/appointment-types`,
    );
    const d = r.data as { items?: AppointmentTypePublic[] };
    return d.items ?? (r.data as AppointmentTypePublic[]);
  },
};
