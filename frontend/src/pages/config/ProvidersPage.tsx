import { useEffect, useState } from "react";
import Table from "@cloudscape-design/components/table";
import Header from "@cloudscape-design/components/header";
import Box from "@cloudscape-design/components/box";
import PageHeader from "../../components/layout/PageHeader";
import { providersApi } from "../../api";
import { useFlash } from "../../context/FlashbarContext";

interface Provider {
  id: string;
  user_id: string;
  display_name?: string;
  email?: string;
  npi?: string | null;
  specialty?: string | null;
  bookable: boolean;
}

export default function ProvidersPage() {
  const { push } = useFlash();
  const [items, setItems] = useState<Provider[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    providersApi.list()
      .then((r: unknown) => setItems(((r as { items?: Provider[] }).items) ?? (r as Provider[])))
      .catch(() => push({ type: "error", content: "Failed to load providers" }))
      .finally(() => setLoading(false));
  }, [push]);

  return (
    <PageHeader
      title="Providers"
      description="Bookable clinicians on your team"
    >
      <Table
        loading={loading}
        items={items}
        columnDefinitions={[
          { id: "name", header: "Name", cell: (p) => p.display_name ?? p.email ?? p.id.slice(0, 8) },
          { id: "email", header: "Email", cell: (p) => p.email ?? "—" },
          { id: "npi", header: "NPI", cell: (p) => p.npi ?? "—" },
          { id: "specialty", header: "Specialty", cell: (p) => p.specialty ?? "—" },
          { id: "bookable", header: "Bookable", cell: (p) => (p.bookable ? "Yes" : "No") },
        ]}
        header={<Header counter={`(${items.length})`}>Providers</Header>}
        empty={<Box textAlign="center" padding="l">No providers configured. Create a staff user with the "provider" role first.</Box>}
      />
    </PageHeader>
  );
}
