import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import Flashbar from "@cloudscape-design/components/flashbar";
const Ctx = createContext(undefined);
export function FlashbarProvider({ children }) {
    const [items, setItems] = useState([]);
    const dismiss = useCallback((id) => {
        setItems((prev) => prev.filter((i) => i.id !== id));
    }, []);
    const push = useCallback((item) => {
        const id = crypto.randomUUID();
        const full = {
            ...item,
            id,
            dismissible: true,
            onDismiss: () => dismiss(id),
        };
        setItems((prev) => [...prev, full]);
    }, [dismiss]);
    const value = useMemo(() => ({ items, push, dismiss }), [items, push, dismiss]);
    return (_jsxs(Ctx.Provider, { value: value, children: [_jsx("div", { style: { position: "fixed", top: 0, left: 0, right: 0, zIndex: 2000 }, children: _jsx(Flashbar, { items: items }) }), children] }));
}
export function useFlash() {
    const ctx = useContext(Ctx);
    if (!ctx)
        throw new Error("useFlash must be used inside FlashbarProvider");
    return ctx;
}
