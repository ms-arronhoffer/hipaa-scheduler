import axios from "axios";
// Distinct storage key so the admin surface does not collide with any staff
// frontend token on the same origin during local dev.
const TOKEN_KEY = "hs_admin_access_token";
const REFRESH_KEY = "hs_admin_refresh_token";
const IMPERSONATE_KEY = "hs_admin_impersonate_token";
export function getToken() {
    return sessionStorage.getItem(IMPERSONATE_KEY) || sessionStorage.getItem(TOKEN_KEY);
}
export function getAdminToken() {
    return sessionStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
    if (token)
        sessionStorage.setItem(TOKEN_KEY, token);
    else
        sessionStorage.removeItem(TOKEN_KEY);
}
export function setRefreshToken(token) {
    if (token)
        sessionStorage.setItem(REFRESH_KEY, token);
    else
        sessionStorage.removeItem(REFRESH_KEY);
}
export function getRefreshToken() {
    return sessionStorage.getItem(REFRESH_KEY);
}
export function setImpersonationToken(token) {
    if (token)
        sessionStorage.setItem(IMPERSONATE_KEY, token);
    else
        sessionStorage.removeItem(IMPERSONATE_KEY);
}
export function getImpersonationToken() {
    return sessionStorage.getItem(IMPERSONATE_KEY);
}
export function clearTokens() {
    setToken(null);
    setRefreshToken(null);
    setImpersonationToken(null);
}
export const apiClient = axios.create({
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
apiClient.interceptors.response.use((r) => r, (err) => {
    if (err.response?.status === 401 && !window.location.pathname.startsWith("/login")) {
        clearTokens();
        window.location.href = "/login";
    }
    return Promise.reject(err);
});
