import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import DatePicker from "@cloudscape-design/components/date-picker";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import Modal from "@cloudscape-design/components/modal";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Table from "@cloudscape-design/components/table";
import { adminApi } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";
function daysUntil(iso) {
    if (!iso)
        return null;
    const ms = new Date(iso).getTime() - Date.now();
    return Math.ceil(ms / 86400000);
}
function baaStatus(row) {
    if (!row.baa_signed_at)
        return _jsx(StatusIndicator, { type: "warning", children: "Not signed" });
    const d = daysUntil(row.baa_expires_at);
    if (d === null)
        return _jsx(StatusIndicator, { type: "success", children: "Signed" });
    if (d < 0)
        return _jsx(StatusIndicator, { type: "error", children: "Expired" });
    if (d < 30)
        return _jsx(StatusIndicator, { type: "warning", children: `Expires in ${d}d` });
    return _jsx(StatusIndicator, { type: "success", children: `${d}d remaining` });
}
export default function BaaTrackingPage() {
    const { push } = useFlash();
    const [rows, setRows] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editing, setEditing] = useState(null);
    const [signed, setSigned] = useState("");
    const [expires, setExpires] = useState("");
    const [docKey, setDocKey] = useState("");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    async function reload() {
        setLoading(true);
        try {
            setRows(await adminApi.listBaa());
        }
        catch {
            push({ type: "error", content: "Failed to load BAA tracking" });
        }
        finally {
            setLoading(false);
        }
    }
    useEffect(() => {
        void reload();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    function openEdit(row) {
        setEditing(row);
        setSigned(row.baa_signed_at ? row.baa_signed_at.slice(0, 10) : "");
        setExpires(row.baa_expires_at ? row.baa_expires_at.slice(0, 10) : "");
        setDocKey(row.baa_document_key ?? "");
        setError(null);
    }
    async function save(e) {
        e.preventDefault();
        if (!editing)
            return;
        setSaving(true);
        setError(null);
        try {
            await adminApi.updateBaa(editing.org_id, {
                baa_signed_at: signed ? new Date(signed).toISOString() : null,
                baa_expires_at: expires ? new Date(expires).toISOString() : null,
                baa_document_key: docKey || null,
            });
            setEditing(null);
            push({ type: "success", content: "BAA record updated." });
            await reload();
        }
        catch (e) {
            const err = e;
            setError(err.response?.data?.detail ?? e.message);
        }
        finally {
            setSaving(false);
        }
    }
    const missing = rows.filter((r) => !r.baa_signed_at).length;
    return (_jsxs(PageHeader, { title: "BAA tracking", description: "Business Associate Agreement status per tenant.", actions: _jsx(Button, { iconName: "refresh", onClick: reload, loading: loading }), children: [_jsxs(SpaceBetween, { size: "l", children: [missing > 0 && (_jsxs(Alert, { type: "warning", children: [missing, " tenant", missing === 1 ? "" : "s", " without a signed BAA. Do not let unsigned tenants process PHI."] })), _jsx(Table, { variant: "container", loading: loading, loadingText: "Loading BAA records", items: rows, columnDefinitions: [
                            { id: "name", header: "Tenant", cell: (r) => r.org_name },
                            { id: "status", header: "Status", cell: baaStatus },
                            {
                                id: "signed",
                                header: "Signed",
                                cell: (r) => (r.baa_signed_at ? new Date(r.baa_signed_at).toLocaleDateString() : "—"),
                            },
                            {
                                id: "expires",
                                header: "Expires",
                                cell: (r) => (r.baa_expires_at ? new Date(r.baa_expires_at).toLocaleDateString() : "—"),
                            },
                            {
                                id: "doc",
                                header: "Document",
                                cell: (r) => (r.baa_document_key ? _jsx("code", { children: r.baa_document_key }) : "—"),
                            },
                            { id: "contact", header: "Contact", cell: (r) => r.contact_email ?? "—" },
                            {
                                id: "actions",
                                header: "",
                                cell: (r) => (_jsx(Button, { variant: "inline-link", onClick: () => openEdit(r), children: "Edit" })),
                            },
                        ], empty: _jsx(Box, { textAlign: "center", color: "inherit", children: _jsx("b", { children: "No tenants yet" }) }) })] }), _jsx(Modal, { visible: !!editing, onDismiss: () => setEditing(null), header: editing ? `BAA — ${editing.org_name}` : "", footer: _jsx(Box, { float: "right", children: _jsxs(SpaceBetween, { direction: "horizontal", size: "xs", children: [_jsx(Button, { variant: "link", onClick: () => setEditing(null), children: "Cancel" }), _jsx(Button, { variant: "primary", loading: saving, onClick: () => void save(new Event("submit")), children: "Save" })] }) }), children: _jsx("form", { onSubmit: save, children: _jsx(Form, { children: _jsxs(SpaceBetween, { size: "m", children: [error && _jsx(Alert, { type: "error", children: error }), _jsx(FormField, { label: "Signed on", children: _jsx(DatePicker, { value: signed, onChange: (e) => setSigned(e.detail.value) }) }), _jsx(FormField, { label: "Expires on", children: _jsx(DatePicker, { value: expires, onChange: (e) => setExpires(e.detail.value) }) }), _jsx(FormField, { label: "Document storage key", description: "Object storage key for the signed PDF.", children: _jsx(Input, { value: docKey, onChange: (e) => setDocKey(e.detail.value) }) })] }) }) }) })] }));
}
