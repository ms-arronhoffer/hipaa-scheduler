import { apiClient } from "./client";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export const patientAuthApi = {
  async requestMagic(email: string): Promise<void> {
    await apiClient.post("/patient-auth/magic/request", { email });
  },

  async consumeMagic(token: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/patient-auth/magic/consume", { token });
    return r.data;
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/patient-auth/login", { email, password });
    return r.data;
  },

  async claim(token: string): Promise<TokenResponse> {
    const r = await apiClient.post<TokenResponse>("/patient-auth/claim", { token });
    return r.data;
  },
};
