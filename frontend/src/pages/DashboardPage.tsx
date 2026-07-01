import { useEffect, useState } from "react";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import Container from "@cloudscape-design/components/container";
import Box from "@cloudscape-design/components/box";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import PageHeader from "../components/layout/PageHeader";
import { useAuth } from "../auth/AuthContext";
import { appointmentsApi, waitlistApi } from "../api";

type Stats = {
  today: number;
  upcoming: number;
  waitlist: number;
};

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<Stats>({ today: 0, upcoming: 0, waitlist: 0 });

  useEffect(() => {
    const now = new Date();
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).toISOString();
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1).toISOString();
    Promise.all([
      appointmentsApi.list({ from_ts: start, to_ts: end }),
      appointmentsApi.list({ from_ts: end }),
      waitlistApi.list().catch(() => ({ items: [] })),
    ]).then(([today, upcoming, waitlist]) => {
      setStats({
        today: today.total ?? today.items?.length ?? 0,
        upcoming: upcoming.total ?? upcoming.items?.length ?? 0,
        waitlist: (waitlist as { items: unknown[] }).items?.length ?? 0,
      });
    }).catch(() => { /* keep zeros on failure */ });
  }, []);

  return (
    <PageHeader
      title={`Welcome, ${user?.first_name ?? user?.email ?? ""}`}
      description="Today at a glance"
    >
      <SpaceBetween size="l">
        <ColumnLayout columns={3} variant="text-grid">
          <Container header={<Header variant="h3">Today's appointments</Header>}>
            <Box variant="h1">{stats.today}</Box>
          </Container>
          <Container header={<Header variant="h3">Upcoming</Header>}>
            <Box variant="h1">{stats.upcoming}</Box>
          </Container>
          <Container header={<Header variant="h3">Waitlist</Header>}>
            <Box variant="h1">{stats.waitlist}</Box>
          </Container>
        </ColumnLayout>
      </SpaceBetween>
    </PageHeader>
  );
}
