import { Link, useParams, useSearchParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SpaceBetween from "@cloudscape-design/components/space-between";
import PageHeader from "../components/layout/PageHeader";

export default function BookedPage() {
  const { slug = "" } = useParams();
  const [params] = useSearchParams();
  const claim = params.get("claim");

  return (
    <PageHeader
      title="You're booked"
      description="A confirmation email is on its way. You can cancel or reschedule from that email."
    >
      <SpaceBetween size="l">
        <Alert type="success" header="Appointment confirmed">
          Please arrive 10 minutes early to complete any intake forms.
        </Alert>

        {claim && (
          <Container header={<Header variant="h2">Claim your account</Header>}>
            <SpaceBetween size="m">
              <Box>
                You booked as a guest. Claim your account now to manage future
                appointments in one place. This link is valid for 24 hours.
              </Box>
              <Box>
                <Link to={`/claim/${claim}`}>Claim my account</Link>
              </Box>
            </SpaceBetween>
          </Container>
        )}

        <Container header={<Header variant="h2">What's next?</Header>}>
          <Box>
            <Link to={`/o/${slug}`}>Back to {slug}</Link>
          </Box>
        </Container>
      </SpaceBetween>
    </PageHeader>
  );
}
