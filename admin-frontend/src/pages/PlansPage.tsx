import { useEffect, useState } from "react";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Table from "@cloudscape-design/components/table";
import { adminApi, Plan } from "../api/admin";
import { useFlash } from "../context/FlashbarContext";
import PageHeader from "../components/layout/PageHeader";

export default function PlansPage() {
  const { push } = useFlash();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true);
    try {
      setPlans(await adminApi.listPlans());
    } catch {
      push({ type: "error", content: "Failed to load plans" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <PageHeader
      title="Plans"
      description="Base subscription tiers. Per-tenant overrides are set from the Tenant detail page."
      actions={
        <SpaceBetween direction="horizontal" size="xs">
          <Button iconName="refresh" onClick={reload} loading={loading} />
        </SpaceBetween>
      }
    >
      <Table
        variant="container"
        loading={loading}
        loadingText="Loading plans"
        items={plans}
        columnDefinitions={[
          { id: "name", header: "Plan", cell: (p) => <code>{p.name}</code> },
          { id: "seat_limit", header: "Seat limit", cell: (p) => p.seat_limit },
          {
            id: "price",
            header: "Monthly price",
            cell: (p) => `$${(p.monthly_price_cents / 100).toFixed(2)}`,
          },
          {
            id: "features",
            header: "Features",
            cell: (p) =>
              Object.entries(p.features || {})
                .filter(([, v]) => v)
                .map(([k]) => k)
                .join(", ") || "—",
          },
        ]}
        empty={
          <Box textAlign="center" color="inherit">
            <b>No plans configured</b>
          </Box>
        }
      />
    </PageHeader>
  );
}
