import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import Badge from "@cloudscape-design/components/badge";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import DatePicker from "@cloudscape-design/components/date-picker";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import Pagination from "@cloudscape-design/components/pagination";
import Select from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import Toggle from "@cloudscape-design/components/toggle";
import { adminApi } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";
const ENTITY_OPTIONS = [
    { value: "", label: "Any entity" },
    { value: "patient", label: "patient" },
    { value: "appointment", label: "appointment" },
    { value: "intake_submission", label: "intake_submission" },
    { value: "document", label: "document" },
    { value: "insurance_policy", label: "insurance_policy" },
    { value: "user", label: "user" },
    { value: "api_key", label: "api_key" },
    { value: "webhook_subscription", label: "webhook_subscription" },
    { value: "organization", label: "organization" },
];
const PAGE_SIZE = 50;
function isoOrNull(date) {
    return date ? new Date(date).toISOString() : undefined;
}
export default function AuditSearchPage() {
    const { push } = useFlash();
    const [tenants, setTenants] = useState([]);
    const [rows, setRows] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [orgId, setOrgId] = useState("");
    const [actorEmail, setActorEmail] = useState("");
    const [entityType, setEntityType] = useState("");
    const [entityId, setEntityId] = useState("");
    const [action, setAction] = useState("");
    const [phiOnly, setPhiOnly] = useState(false);
    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");
    useEffect(() => {
        void (async () => {
            try {
                setTenants(await adminApi.listTenants());
            }
            catch {
                /* non-fatal */
            }
        })();
    }, []);
    async function runSearch(e, targetPage = 1) {
        if (e)
            e.preventDefault();
        setLoading(true);
        try {
            const params = {
                org_id: orgId || undefined,
                actor_email: actorEmail || undefined,
                entity_type: entityType || undefined,
                entity_id: entityId || undefined,
                action: action || undefined,
                phi_only: phiOnly || undefined,
                from_ts: isoOrNull(fromDate),
                to_ts: isoOrNull(toDate),
                page: targetPage,
                page_size: PAGE_SIZE,
            };
            const res = await adminApi.searchAudit(params);
            setRows(res.items);
            setTotal(res.total);
            setPage(targetPage);
        }
        catch {
            push({ type: "error", content: "Audit search failed" });
        }
        finally {
            setLoading(false);
        }
    }
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const tenantName = (id) => tenants.find((t) => t.id === id)?.name ?? id;
    return (_jsx(PageHeader, { title: "Audit search", description: "Cross-tenant PHI access and administrative actions. Every row is immutable.", children: _jsxs(SpaceBetween, { size: "l", children: [_jsx("form", { onSubmit: (e) => runSearch(e, 1), children: _jsx(Form, { actions: _jsx(SpaceBetween, { direction: "horizontal", size: "xs", children: _jsx(Button, { variant: "primary", formAction: "submit", loading: loading, children: "Search" }) }), header: _jsx(Header, { variant: "h2", children: "Filters" }), children: _jsxs(SpaceBetween, { size: "m", children: [_jsxs(SpaceBetween, { direction: "horizontal", size: "s", children: [_jsx(FormField, { label: "Tenant", children: _jsx(Select, { selectedOption: orgId
                                                    ? { value: orgId, label: tenantName(orgId) }
                                                    : { value: "", label: "All tenants" }, options: [
                                                    { value: "", label: "All tenants" },
                                                    ...tenants.map((t) => ({ value: t.id, label: t.name })),
                                                ], onChange: (e) => setOrgId(e.detail.selectedOption.value ?? "") }) }), _jsx(FormField, { label: "Entity type", children: _jsx(Select, { selectedOption: ENTITY_OPTIONS.find((o) => o.value === entityType) ?? ENTITY_OPTIONS[0], options: ENTITY_OPTIONS, onChange: (e) => setEntityType(e.detail.selectedOption.value ?? "") }) }), _jsx(FormField, { label: "Actor email", children: _jsx(Input, { value: actorEmail, onChange: (e) => setActorEmail(e.detail.value) }) }), _jsx(FormField, { label: "Entity ID", children: _jsx(Input, { value: entityId, onChange: (e) => setEntityId(e.detail.value) }) }), _jsx(FormField, { label: "Action", children: _jsx(Input, { value: action, onChange: (e) => setAction(e.detail.value), placeholder: "read, create, update, delete" }) })] }), _jsxs(SpaceBetween, { direction: "horizontal", size: "s", children: [_jsx(FormField, { label: "From", children: _jsx(DatePicker, { value: fromDate, onChange: (e) => setFromDate(e.detail.value) }) }), _jsx(FormField, { label: "To", children: _jsx(DatePicker, { value: toDate, onChange: (e) => setToDate(e.detail.value) }) }), _jsx(FormField, { label: "PHI accessed only", children: _jsx(Toggle, { checked: phiOnly, onChange: (e) => setPhiOnly(e.detail.checked), children: phiOnly ? "On" : "Off" }) })] })] }) }) }), _jsx(Table, { variant: "container", header: _jsx(Header, { counter: `(${total})`, children: "Results" }), loading: loading, loadingText: "Searching", items: rows, trackBy: "id", columnDefinitions: [
                        {
                            id: "ts",
                            header: "Time",
                            cell: (r) => new Date(r.created_at).toLocaleString(),
                        },
                        { id: "tenant", header: "Tenant", cell: (r) => tenantName(r.org_id) },
                        { id: "actor", header: "Actor", cell: (r) => r.actor_email ?? r.actor_type },
                        { id: "entity", header: "Entity", cell: (r) => `${r.entity_type} ${r.entity_id ?? ""}` },
                        { id: "action", header: "Action", cell: (r) => r.action },
                        {
                            id: "phi",
                            header: "PHI",
                            cell: (r) => (r.phi_accessed ? _jsx(Badge, { color: "red", children: "PHI" }) : _jsx(Badge, { color: "grey", children: "no" })),
                        },
                        { id: "ip", header: "IP", cell: (r) => r.ip ?? "—" },
                        {
                            id: "detail",
                            header: "Detail",
                            cell: (r) => r.changes ? (_jsx(ExpandableSection, { headerText: "View", children: _jsx("pre", { style: { margin: 0, fontSize: 12, whiteSpace: "pre-wrap" }, children: JSON.stringify(r.changes, null, 2) }) })) : ("—"),
                        },
                    ], pagination: _jsx(Pagination, { currentPageIndex: page, pagesCount: pageCount, onChange: (e) => void runSearch(undefined, e.detail.currentPageIndex) }), empty: _jsxs(Box, { textAlign: "center", color: "inherit", children: [_jsx("b", { children: "No results" }), _jsx(Box, { variant: "p", children: "Run a search to see cross-tenant audit rows." })] }) })] }) }));
}
