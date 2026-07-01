import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import { publicApi, OrgPublic } from "../api/publicBooking";
import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/layout/PageHeader";

export default function OrgLandingPage() {
  const { slug = "" } = useParams();
  const nav = useNavigate();
  const { isAuthenticated } = useAuth();
  const [org, setOrg] = useState<OrgPublic | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const o = await publicApi.getOrg(slug);
        if (mounted) setOrg(o);
      } catch {
        if (mounted) setErr("We couldn't find that practice. Please check the link.");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [slug]);

  if (loading) {
    return (
      <Box textAlign="center" padding="xxl">
        <Spinner size="large" />
      </Box>
    );
  }

  if (err || !org) {
    return (
      <PageHeader title="Practice not found">
        <Alert type="error">{err ?? "Unknown error"}</Alert>
      </PageHeader>
    );
  }

  return (
    <PageHeader title={org.name} description="Book, reschedule, or cancel your appointment.">
      <SpaceBetween size="l">
        <Container header={<Header variant="h2">Book an appointment</Header>}>
          <SpaceBetween size="m">
            <Box>
              If you already have an account with {org.name}, sign in to book. Otherwise
              you can book as a guest — you'll be able to claim the account afterward.
            </Box>
            <SpaceBetween direction="horizontal" size="s">
              {isAuthenticated ? (
                <Button variant="primary" onClick={() => nav(`/o/${slug}/book`)}>
                  Book with my account
                </Button>
              ) : (
                <Button variant="primary" onClick={() => nav("/login")}>
                  Sign in to book
                </Button>
              )}
              <Button onClick={() => nav(`/o/${slug}/book/guest`)}>Continue as guest</Button>
            </SpaceBetween>
          </SpaceBetween>
        </Container>

        <Container header={<Header variant="h2">Already have an appointment?</Header>}>
          <Box>
            <Link to="/login">Sign in</Link> to view, reschedule, or cancel your upcoming
            appointments. New patients will receive an email link after their first visit
            to claim their account.
          </Box>
        </Container>
      </SpaceBetween>
    </PageHeader>
  );
}
