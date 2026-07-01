import { apiClient } from "./client";

export interface LoginResponse {
  access_token?: string;
  refresh_token?: string;
  mfa_required?: boolean;
  mfa_ticket?: string;
}

export const authApi = {
  login: (email: string, password: string) =>
    apiClient.post<LoginResponse>("/auth/login", { email, password }).then((r) => r.data),
  verifyMfa: (ticket: string, code: string) =>
    apiClient.post<LoginResponse>("/auth/mfa/verify", { ticket, code }).then((r) => r.data),
  me: () => apiClient.get<CurrentUser>("/auth/me").then((r) => r.data),
  logout: () => apiClient.post("/auth/logout").then((r) => r.data),
  refresh: (refresh_token: string) =>
    apiClient.post<LoginResponse>("/auth/refresh", { refresh_token }).then((r) => r.data),
};

export interface CurrentUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  roles: string[];
  is_super_admin: boolean;
  mfa_enrolled: boolean;
  org_id: string | null;
}
