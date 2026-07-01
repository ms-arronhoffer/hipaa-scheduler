import { Link } from "react-router-dom";
import Box from "@cloudscape-design/components/box";
import PageHeader from "../components/layout/PageHeader";

export default function NotFoundPage() {
  return (
    <PageHeader title="Not found" description="This page does not exist.">
      <Box>
        <Link to="/login">Sign in</Link>
      </Box>
    </PageHeader>
  );
}
