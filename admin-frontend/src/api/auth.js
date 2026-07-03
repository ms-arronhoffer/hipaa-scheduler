import { apiClient } from "./client";
export const authApi = {
    login: (email, password) => apiClient.post("/auth/login", { email, password }).then((r) => r.data),
    verifyMfa: (ticket, code) => apiClient.post("/auth/mfa/verify", { ticket, code }).then((r) => r.data),
    me: () => apiClient.get("/auth/me").then((r) => r.data),
    logout: () => apiClient.post("/auth/logout").then((r) => r.data),
};
