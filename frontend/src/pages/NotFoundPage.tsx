import { Link } from "react-router-dom";
import Box from "@cloudscape-design/components/box";
import SpaceBetween from "@cloudscape-design/components/space-between";

export default function NotFoundPage() {
  return (
    <Box padding={{ vertical: "xxxl", horizontal: "l" }} textAlign="center">
      <SpaceBetween size="m">
        <Box variant="h1">404 · Page not found</Box>
        <Box color="text-body-secondary">The page you're looking for doesn't exist.</Box>
        <Link to="/dashboard">Back to dashboard</Link>
      </SpaceBetween>
    </Box>
  );
}
