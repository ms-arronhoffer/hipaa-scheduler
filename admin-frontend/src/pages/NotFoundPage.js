import { jsx as _jsx } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import Box from "@cloudscape-design/components/box";
import PageHeader from "../components/layout/PageHeader";
export default function NotFoundPage() {
    return (_jsx(PageHeader, { title: "Not found", description: "This admin route does not exist.", children: _jsx(Box, { children: _jsx(Link, { to: "/tenants", children: "Back to tenants" }) }) }));
}
