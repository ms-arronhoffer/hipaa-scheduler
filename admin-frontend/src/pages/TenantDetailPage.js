import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Modal from "@cloudscape-design/components/modal";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Toggle from "@cloudscape-design/components/toggle";
import { adminApi } from "../api/admin";
import { useAuth } from "../auth/AuthContext";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";
function Field({ label, value }) {
    return (_jsxs("div", { children: [_jsx(Box, { variant: "awsui-key-label", children: label }), _jsx("div", { children: value })] }));
}
export default function TenantDetailPage() {
    const { id = "" } = useParams();
    const nav = useNavigate();
    const { push } = useFlash();
    const { beginImpersonation } = useAuth();
    const [tenant, setTenant] = useState(null);
    const [plans, setPlans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showPlanOverride, setShowPlanOverride] = useState(false);
    const [showSeatOverride, setShowSeatOverride] = useState(false);
    const [showImpersonate, setShowImpersonate] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [newPlan, setNewPlan] = useState("");
    const [newSeats, setNewSeats] = useState(0);
    const [reason, setReason] = useState("");
    async function reload() {
        setLoading(true);
        try {
            const [t, p] = await Promise.all([adminApi.getTenant(id), adminApi.listPlans()]);
            setTenant(t);
            setPlans(p);
            setNewPlan(t.plan);
            setNewSeats(t.seats);
        }
        catch {
            push({ type: "error", content: "Failed to load tenant" });
        }
        finally {
            setLoading(false);
        }
    }
    useEffect(() => {
        void reload();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [id]);
    async function toggleMfa(mfa_required) {
        try {
            const t = await adminApi.updateTenant(id, { mfa_required });
            setTenant(t);
            push({ type: "success", content: "MFA policy updated." });
        }
        catch {
            push({ type: "error", content: "Failed to update MFA policy." });
        }
    }
    async function toggleActive() {
        if (!tenant)
            return;
        try {
            const t = tenant.active
                ? await adminApi.suspendTenant(id)
                : await adminApi.activateTenant(id);
            setTenant(t);
            push({
                type: "success",
                content: t.active ? "Tenant activated." : "Tenant suspended.",
            });
        }
        catch {
            push({ type: "error", content: "Failed to change tenant status." });
        }
    }
    async function submitPlanOverride(e) {
        e.preventDefault();
        setError(null);
        setSaving(true);
        try {
            const plan = plans.find((p) => p.name === newPlan);
            if (!plan)
                throw new Error("Unknown plan");
            const t = await adminApi.overridePlan(id, plan.id);
            setTenant(t);
            setShowPlanOverride(false);
            push({ type: "success", content: "Plan override applied." });
        }
        catch (e) {
            setError(e.message);
        }
        finally {
            setSaving(false);
        }
    }
    async function submitSeatOverride(e) {
        e.preventDefault();
        setError(null);
        setSaving(true);
        try {
            const t = await adminApi.overrideSeats(id, newSeats);
            setTenant(t);
            setShowSeatOverride(false);
            push({ type: "success", content: `Seat cap set to ${t.seats}.` });
        }
        catch (e) {
            setError(e.message);
        }
        finally {
            setSaving(false);
        }
    }
    async function submitImpersonate(e) {
        e.preventDefault();
        if (!reason.trim()) {
            setError("A reason is required for the audit log.");
            return;
        }
        setError(null);
        setSaving(true);
        try {
            const res = await adminApi.impersonate(id, undefined, reason);
            await beginImpersonation(res.access_token);
            setShowImpersonate(false);
            push({
                type: "warning",
                content: "Impersonation session active. All actions are logged.",
            });
            window.location.href = "/";
        }
        catch (e) {
            const err = e;
            setError(err.response?.data?.detail ?? e.message);
        }
        finally {
            setSaving(false);
        }
    }
    if (loading || !tenant) {
        return _jsx(PageHeader, { title: "Tenant", children: "Loading\u2026" });
    }
    return (_jsxs(PageHeader, { title: tenant.name, description: tenant.slug, actions: _jsxs(SpaceBetween, { direction: "horizontal", size: "xs", children: [_jsx(Button, { onClick: () => nav("/tenants"), children: "Back" }), _jsx(Button, { onClick: reload, iconName: "refresh" }), _jsx(Button, { onClick: () => setShowImpersonate(true), variant: "normal", children: "Impersonate" }), _jsx(Button, { onClick: toggleActive, variant: tenant.active ? "normal" : "primary", children: tenant.active ? "Suspend" : "Activate" })] }), children: [_jsxs(SpaceBetween, { size: "l", children: [_jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Overview" }), children: _jsxs(ColumnLayout, { columns: 3, variant: "text-grid", children: [_jsx(Field, { label: "Plan", value: _jsx("code", { children: tenant.plan }) }), _jsx(Field, { label: "Seats", value: `${tenant.seats_used} / ${tenant.seats}` }), _jsx(Field, { label: "Status", value: tenant.active ? (_jsx(StatusIndicator, { type: "success", children: "Active" })) : (_jsx(StatusIndicator, { type: "error", children: "Suspended" })) }), _jsx(Field, { label: "BAA", value: tenant.baa_signed_at ? (_jsxs(StatusIndicator, { type: "success", children: ["Signed ", new Date(tenant.baa_signed_at).toLocaleDateString()] })) : (_jsx(StatusIndicator, { type: "warning", children: "Not signed" })) }), _jsx(Field, { label: "Created", value: new Date(tenant.created_at).toLocaleString() }), _jsx(Field, { label: "Org ID", value: _jsx("code", { children: tenant.id }) })] }) }), _jsx(Container, { header: _jsx(Header, { variant: "h2", actions: _jsxs(SpaceBetween, { direction: "horizontal", size: "xs", children: [_jsx(Button, { onClick: () => setShowPlanOverride(true), children: "Override plan" }), _jsx(Button, { onClick: () => setShowSeatOverride(true), children: "Override seats" })] }), children: "Plan & seats" }), children: _jsx(Box, { variant: "p", children: "Overrides bypass the plan defaults for this tenant only. Use them for trial extensions or exception-based deals. The change is written to the cross-tenant audit log." }) }), _jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Security" }), children: _jsx(SpaceBetween, { size: "m", children: _jsx(FormField, { label: "Require MFA for privileged staff", description: "Applies to practice_admin, provider, and billing roles.", children: _jsx(Toggle, { checked: tenant.mfa_required, onChange: (e) => void toggleMfa(e.detail.checked), children: tenant.mfa_required ? "Required" : "Optional" }) }) }) })] }), _jsx(Modal, { visible: showPlanOverride, onDismiss: () => setShowPlanOverride(false), header: "Override plan", footer: _jsx(Box, { float: "right", children: _jsxs(SpaceBetween, { direction: "horizontal", size: "xs", children: [_jsx(Button, { variant: "link", onClick: () => setShowPlanOverride(false), children: "Cancel" }), _jsx(Button, { variant: "primary", loading: saving, onClick: () => void submitPlanOverride(new Event("submit")), children: "Apply" })] }) }), children: _jsx("form", { onSubmit: submitPlanOverride, children: _jsx(Form, { children: _jsxs(SpaceBetween, { size: "m", children: [error && _jsx(Alert, { type: "error", children: error }), _jsx(FormField, { label: "Plan", children: _jsx(Select, { selectedOption: { value: newPlan, label: newPlan }, options: plans.map((p) => ({ value: p.name, label: p.name })), onChange: (e) => setNewPlan(e.detail.selectedOption.value ?? "") }) })] }) }) }) }), _jsx(Modal, { visible: showSeatOverride, onDismiss: () => setShowSeatOverride(false), header: "Override seat cap", footer: _jsx(Box, { float: "right", children: _jsxs(SpaceBetween, { direction: "horizontal", size: "xs", children: [_jsx(Button, { variant: "link", onClick: () => setShowSeatOverride(false), children: "Cancel" }), _jsx(Button, { variant: "primary", loading: saving, onClick: () => void submitSeatOverride(new Event("submit")), children: "Apply" })] }) }), children: _jsx("form", { onSubmit: submitSeatOverride, children: _jsx(Form, { children: _jsxs(SpaceBetween, { size: "m", children: [error && _jsx(Alert, { type: "error", children: error }), _jsx(FormField, { label: "Seats", description: `Currently using ${tenant.seats_used}.`, children: _jsx(Input, { type: "number", value: String(newSeats), onChange: (e) => setNewSeats(Number(e.detail.value) || 0) }) })] }) }) }) }), _jsx(Modal, { visible: showImpersonate, onDismiss: () => setShowImpersonate(false), header: "Impersonate tenant", footer: _jsx(Box, { float: "right", children: _jsxs(SpaceBetween, { direction: "horizontal", size: "xs", children: [_jsx(Button, { variant: "link", onClick: () => setShowImpersonate(false), children: "Cancel" }), _jsx(Button, { variant: "primary", loading: saving, onClick: () => void submitImpersonate(new Event("submit")), children: "Start impersonation" })] }) }), children: _jsx("form", { onSubmit: submitImpersonate, children: _jsx(Form, { children: _jsxs(SpaceBetween, { size: "m", children: [_jsxs(Alert, { type: "warning", statusIconAriaLabel: "Warning", children: ["You are about to act as an administrator of", " ", _jsx("strong", { children: tenant.name }), ". All actions taken during the session are recorded to the audit log for this tenant and the super-admin log. Sessions expire after 15 minutes."] }), error && _jsx(Alert, { type: "error", children: error }), _jsx(FormField, { label: "Reason", description: "Required for the audit trail.", children: _jsx(Input, { value: reason, onChange: (e) => setReason(e.detail.value) }) })] }) }) }) })] }));
}
