import axios, { AxiosError } from "axios";

const TOKEN_KEY = "hs_patient_access_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 20_000,
});

apiClient.interceptors.request.use((config) => {
  const t = getToken();
  if (t) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401) {
      const path = window.location.pathname;
      const isPublic =
        path === "/login" ||
        path.startsWith("/o/") ||
        path.startsWith("/magic/") ||
        path.startsWith("/claim/");
      if (!isPublic) {
        clearToken();
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);
