import { apiClient } from "./client";

/**
 * Authenticated patient self-service endpoints (`/pub/me/...`).
 * All calls require a patient JWT (added by the client interceptor).
 */

export interface Consent {
  id: string;
  org_id: string;
  patient_id: string;
  kind: string;
  document_version: string;
  body_hash: string;
  signed_at: string;
  signer_name: string;
  signer_ip: string | null;
}

export interface ConsentSignRequest {
  kind: string;
  document_version: string;
  body_hash: string;
  signer_name: string;
}

export interface PatientDocument {
  id: string;
  org_id: string;
  patient_id: string;
  kind: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

export interface IntakeForm {
  id: string;
  org_id: string;
  name: string;
  version: number;
  schema: Record<string, unknown>;
  active: boolean;
}

export interface IntakeSubmission {
  id: string;
  org_id: string;
  form_id: string;
  form_version: number;
  patient_id: string;
  appointment_id: string | null;
  answers: Record<string, unknown>;
  signed_at: string | null;
  signature_name: string | null;
  created_at: string;
}

export interface IntakeSubmitRequest {
  form_id: string;
  appointment_id?: string | null;
  answers: Record<string, unknown>;
  signature_name?: string | null;
}

export interface PortalSession {
  email: string;
  auth_mode: string;
  mfa_enrolled: boolean;
  last_login_at: string | null;
  sessions_invalid_after: string | null;
  current_session_issued_at: string | null;
}

export const portalApi = {
  async listConsents(): Promise<Consent[]> {
    const r = await apiClient.get<Consent[]>("/pub/me/consents");
    return r.data;
  },

  async signConsent(body: ConsentSignRequest): Promise<Consent> {
    const r = await apiClient.post<Consent>("/pub/me/consents", body);
    return r.data;
  },

  async listDocuments(): Promise<PatientDocument[]> {
    const r = await apiClient.get<PatientDocument[]>("/pub/me/documents");
    return r.data;
  },

  async listForms(): Promise<IntakeForm[]> {
    const r = await apiClient.get<IntakeForm[]>("/pub/me/intake/forms");
    return r.data;
  },

  async listSubmissions(): Promise<IntakeSubmission[]> {
    const r = await apiClient.get<IntakeSubmission[]>("/pub/me/intake/submissions");
    return r.data;
  },

  async submitIntake(body: IntakeSubmitRequest): Promise<IntakeSubmission> {
    const r = await apiClient.post<IntakeSubmission>("/pub/me/intake/submissions", body);
    return r.data;
  },

  async session(): Promise<PortalSession> {
    const r = await apiClient.get<PortalSession>("/pub/me/security");
    return r.data;
  },

  async signOutEverywhere(): Promise<void> {
    await apiClient.post("/pub/me/security/sign-out-everywhere");
  },
};
