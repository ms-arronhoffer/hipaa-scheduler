import { jsx as _jsx } from "react/jsx-runtime";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Header from "@cloudscape-design/components/header";
export default function PageHeader({ title, description, actions, children, }) {
    return (_jsx(ContentLayout, { header: _jsx(Header, { variant: "h1", description: description, actions: actions, children: title }), children: children }));
}
