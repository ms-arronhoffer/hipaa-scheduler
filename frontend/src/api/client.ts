import axios, { AxiosError, AxiosInstance } from "axios";

// Session-only token storage. On 401 we clear and bounce to /login. Do not
// switch to localStorage without reviewing XSS surface — Cloudscape apps
// still render arbitrary text fields.
const TOKEN_KEY = "hs_access_token";
const REFRESH_KEY = "hs_refresh_token";

export function getToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string | null) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}
export function setRefreshToken(token: string | null) {
  if (token) sessionStorage.setItem(REFRESH_KEY, token);
  else sessionStorage.removeItem(REFRESH_KEY);
}
export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY);
}
export function clearTokens() {
  setToken(null);
  setRefreshToken(null);
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  headers: { "Content-Type": "application/json" },
  timeout: 30_000,
});

apiClient.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  (err: AxiosError) => {
    if (err.response?.status === 401 && !window.location.pathname.startsWith("/login")) {
      clearTokens();
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);
