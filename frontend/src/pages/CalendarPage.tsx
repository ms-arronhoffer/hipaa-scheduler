import { useCallback, useEffect, useMemo, useState } from "react";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import SegmentedControl from "@cloudscape-design/components/segmented-control";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import PageHeader from "../components/layout/PageHeader";
import { Appointment, appointmentsApi } from "../api";
import { useFlash } from "../context/FlashbarContext";

type View = "day" | "week";

function startOfDay(d: Date) { return new Date(d.getFullYear(), d.getMonth(), d.getDate()); }
function addDays(d: Date, n: number) { const c = new Date(d); c.setDate(c.getDate() + n); return c; }

const HOURS = Array.from({ length: 12 }, (_, i) => 7 + i); // 7am–6pm

export default function CalendarPage() {
  const { push } = useFlash();
  const [view, setView] = useState<View>("week");
  const [anchor, setAnchor] = useState(startOfDay(new Date()));
  const [items, setItems] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(false);

  const { from, to, days } = useMemo(() => {
    const days = view === "day" ? [anchor] : Array.from({ length: 7 }, (_, i) => addDays(anchor, i));
    return { from: days[0], to: addDays(days[days.length - 1], 1), days };
  }, [anchor, view]);

  const load = useCallback(() => {
    setLoading(true);
    appointmentsApi
      .list({ from_ts: from.toISOString(), to_ts: to.toISOString() })
      .then((r) => setItems(r.items ?? []))
      .catch(() => push({ type: "error", content: "Failed to load calendar" }))
      .finally(() => setLoading(false));
  }, [from, to, push]);

  useEffect(() => { load(); }, [load]);

  function apptsForDayHour(day: Date, hour: number) {
    return items.filter((a) => {
      const s = new Date(a.start_at);
      return s.getFullYear() === day.getFullYear()
        && s.getMonth() === day.getMonth()
        && s.getDate() === day.getDate()
        && s.getHours() === hour;
    });
  }

  return (
    <PageHeader
      title="Calendar"
      description="Provider and resource schedule"
      actions={
        <SpaceBetween direction="horizontal" size="xs">
          <Button iconName="angle-left" onClick={() => setAnchor(addDays(anchor, view === "day" ? -1 : -7))} />
          <Button onClick={() => setAnchor(startOfDay(new Date()))}>Today</Button>
          <Button iconName="angle-right" onClick={() => setAnchor(addDays(anchor, view === "day" ? 1 : 7))} />
          <SegmentedControl
            selectedId={view}
            options={[{ id: "day", text: "Day" }, { id: "week", text: "Week" }]}
            onChange={({ detail }) => setView(detail.selectedId as View)}
          />
        </SpaceBetween>
      }
    >
      <Container header={<Header variant="h2">{days[0].toLocaleDateString(undefined, { month: "long", year: "numeric" })}</Header>}>
        {loading ? (
          <Box textAlign="center" padding="xxl"><Spinner size="large" /></Box>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed", minWidth: 720 }}>
              <thead>
                <tr>
                  <th style={{ width: 70, textAlign: "left", padding: "8px", borderBottom: "1px solid #e9ebed" }}>Time</th>
                  {days.map((d) => (
                    <th key={d.toISOString()} style={{ padding: "8px", borderBottom: "1px solid #e9ebed", textAlign: "left" }}>
                      {d.toLocaleDateString(undefined, { weekday: "short", month: "numeric", day: "numeric" })}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {HOURS.map((h) => (
                  <tr key={h}>
                    <td style={{ padding: "8px", verticalAlign: "top", borderBottom: "1px solid #f2f3f3", fontSize: 12, color: "#5f6b7a" }}>
                      {h}:00
                    </td>
                    {days.map((d) => {
                      const cells = apptsForDayHour(d, h);
                      return (
                        <td key={d.toISOString() + h} style={{ padding: "4px", verticalAlign: "top", borderBottom: "1px solid #f2f3f3", height: 56 }}>
                          {cells.map((a) => (
                            <div key={a.id} style={{
                              background: a.status === "canceled" ? "#f2f3f3" : "#e8f0fe",
                              borderLeft: "3px solid #0972d3",
                              padding: "4px 6px",
                              marginBottom: 2,
                              fontSize: 12,
                              borderRadius: 2,
                            }}>
                              {new Date(a.start_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
                              <div style={{ opacity: 0.7 }}>{a.status}</div>
                            </div>
                          ))}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Container>
    </PageHeader>
  );
}
