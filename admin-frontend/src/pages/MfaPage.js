import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { authApi } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
export default function MfaPage() {
    const nav = useNavigate();
    const location = useLocation();
    const { login } = useAuth();
    const state = location.state ?? {};
    const [code, setCode] = useState("");
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);
    async function submit(e) {
        e.preventDefault();
        if (!state.ticket) {
            nav("/login", { replace: true });
            return;
        }
        setError(null);
        setLoading(true);
        try {
            const res = await authApi.verifyMfa(state.ticket, code);
            if (!res.access_token) {
                setError("Unexpected response");
                return;
            }
            await login(res.access_token, res.refresh_token);
            nav(state.from ?? "/tenants", { replace: true });
        }
        catch (e) {
            const ax = e;
            setError(ax.response?.data?.detail ?? "Invalid verification code");
        }
        finally {
            setLoading(false);
        }
    }
    return (_jsx(Box, { padding: { vertical: "xxxl", horizontal: "l" }, children: _jsx("div", { style: { maxWidth: 420, margin: "0 auto" }, children: _jsx(Container, { header: _jsx(Header, { variant: "h1", children: "Two-factor code" }), children: _jsx("form", { onSubmit: submit, children: _jsx(Form, { actions: _jsx(SpaceBetween, { direction: "horizontal", size: "xs", children: _jsx(Button, { variant: "primary", formAction: "submit", loading: loading, children: "Verify" }) }), children: _jsxs(SpaceBetween, { size: "l", children: [error && _jsx(Alert, { type: "error", children: error }), _jsx(FormField, { label: "Authenticator code", children: _jsx(Input, { value: code, onChange: (e) => setCode(e.detail.value), autoFocus: true, inputMode: "numeric" }) })] }) }) }) }) }) }));
}
