import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import { adminApi } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";
function KV({ label, value }) {
    return (_jsxs("div", { children: [_jsx(Box, { variant: "awsui-key-label", children: label }), _jsx("div", { children: value })] }));
}
function ok(v) {
    return v ? (_jsx(StatusIndicator, { type: "success", children: "OK" })) : (_jsx(StatusIndicator, { type: "error", children: "Down" }));
}
export default function SystemHealthPage() {
    const { push } = useFlash();
    const [h, setH] = useState(null);
    const [loading, setLoading] = useState(true);
    async function reload() {
        setLoading(true);
        try {
            setH(await adminApi.systemHealth());
        }
        catch {
            push({ type: "error", content: "Failed to load system health" });
        }
        finally {
            setLoading(false);
        }
    }
    useEffect(() => {
        void reload();
        const timer = window.setInterval(() => void reload(), 30_000);
        return () => window.clearInterval(timer);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    return (_jsx(PageHeader, { title: "System health", description: "Live view of core subsystems. Refreshes every 30 seconds.", actions: _jsx(Button, { iconName: "refresh", onClick: reload, loading: loading }), children: _jsxs(SpaceBetween, { size: "l", children: [_jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Database" }), children: _jsxs(ColumnLayout, { columns: 2, variant: "text-grid", children: [_jsx(KV, { label: "Status", value: h ? ok(h.database.ok) : "—" }), _jsx(KV, { label: "Latency", value: h ? `${h.database.latency_ms} ms` : "—" })] }) }), _jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Scheduler" }), children: _jsxs(ColumnLayout, { columns: 3, variant: "text-grid", children: [_jsx(KV, { label: "Status", value: h ? ok(h.scheduler.ok) : "—" }), _jsx(KV, { label: "Jobs registered", value: h?.scheduler.jobs_registered ?? "—" }), _jsx(KV, { label: "Next run", value: h?.scheduler.next_run_at ? new Date(h.scheduler.next_run_at).toLocaleString() : "—" })] }) }), _jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Webhook queue" }), children: _jsxs(ColumnLayout, { columns: 2, variant: "text-grid", children: [_jsx(KV, { label: "Pending", value: h?.webhook_queue.pending ?? "—" }), _jsx(KV, { label: "Failed (24h)", value: h ? (h.webhook_queue.failed_last_24h > 0 ? (_jsx(StatusIndicator, { type: "warning", children: h.webhook_queue.failed_last_24h })) : (_jsx(StatusIndicator, { type: "success", children: "0" }))) : ("—") })] }) }), _jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Object storage" }), children: _jsx(ColumnLayout, { columns: 1, variant: "text-grid", children: _jsx(KV, { label: "Status", value: h ? ok(h.storage.ok) : "—" }) }) }), _jsx(Container, { header: _jsx(Header, { variant: "h2", children: "Build" }), children: _jsxs(ColumnLayout, { columns: 3, variant: "text-grid", children: [_jsx(KV, { label: "Version", value: h ? _jsx("code", { children: h.build.version }) : "—" }), _jsx(KV, { label: "Commit", value: h ? _jsx("code", { children: h.build.commit }) : "—" }), _jsx(KV, { label: "Started", value: h ? new Date(h.build.started_at).toLocaleString() : "—" })] }) })] }) }));
}
