import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Alert from "@cloudscape-design/components/alert";
import { authApi } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
export default function LoginPage() {
    const nav = useNavigate();
    const location = useLocation();
    const { login } = useAuth();
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    const from = location.state?.from ?? "/tenants";
    async function submit(e) {
        e.preventDefault();
        setError(null);
        setLoading(true);
        try {
            const res = await authApi.login(email, password);
            if (res.mfa_required && res.mfa_ticket) {
                nav("/mfa", { state: { ticket: res.mfa_ticket, from } });
                return;
            }
            if (!res.access_token) {
                setError("Unexpected login response");
                return;
            }
            await login(res.access_token, res.refresh_token);
            nav(from, { replace: true });
        }
        catch (e) {
            const ax = e;
            const msg = e.message === "Super-admin access required"
                ? "This account is not a super-admin."
                : ax.response?.data?.detail ?? "Invalid email or password";
            setError(msg);
        }
        finally {
            setLoading(false);
        }
    }
    return (_jsx(Box, { padding: { vertical: "xxxl", horizontal: "l" }, children: _jsx("div", { style: { maxWidth: 420, margin: "0 auto" }, children: _jsx(Container, { header: _jsx(Header, { variant: "h1", description: "Super-admin console", children: "Sign in" }), children: _jsx("form", { onSubmit: submit, children: _jsx(Form, { actions: _jsx(SpaceBetween, { direction: "horizontal", size: "xs", children: _jsx(Button, { variant: "primary", formAction: "submit", loading: loading, children: "Sign in" }) }), children: _jsxs(SpaceBetween, { size: "l", children: [error && _jsx(Alert, { type: "error", children: error }), _jsx(FormField, { label: "Email", children: _jsx(Input, { value: email, onChange: (e) => setEmail(e.detail.value), type: "email", autoFocus: true }) }), _jsx(FormField, { label: "Password", children: _jsx(Input, { value: password, onChange: (e) => setPassword(e.detail.value), type: "password" }) })] }) }) }) }) }) }));
}
