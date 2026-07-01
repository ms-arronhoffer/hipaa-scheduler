import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from "react";
import Flashbar, { FlashbarProps } from "@cloudscape-design/components/flashbar";

type FlashItem = FlashbarProps.MessageDefinition;

type FlashCtx = {
  items: FlashItem[];
  push: (item: Omit<FlashItem, "id" | "onDismiss">) => void;
  dismiss: (id: string) => void;
};

const Ctx = createContext<FlashCtx | undefined>(undefined);

export function FlashbarProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<FlashItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }, []);

  const push = useCallback(
    (item: Omit<FlashItem, "id" | "onDismiss">) => {
      const id = crypto.randomUUID();
      const full: FlashItem = {
        ...item,
        id,
        dismissible: true,
        onDismiss: () => dismiss(id),
      };
      setItems((prev) => [...prev, full]);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ items, push, dismiss }), [items, push, dismiss]);

  return (
    <Ctx.Provider value={value}>
      <div style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 2000 }}>
        <Flashbar items={items} />
      </div>
      {children}
    </Ctx.Provider>
  );
}

export function useFlash() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFlash must be used inside FlashbarProvider");
  return ctx;
}
