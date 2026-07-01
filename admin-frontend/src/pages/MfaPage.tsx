import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AxiosError } from "axios";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { authApi } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export default function MfaPage() {
  const nav = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const state = (location.state as { ticket?: string; from?: string } | null) ?? {};
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!state.ticket) {
      nav("/login", { replace: true });
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.verifyMfa(state.ticket, code);
      if (!res.access_token) {
        setError("Unexpected response");
        return;
      }
      await login(res.access_token, res.refresh_token);
      nav(state.from ?? "/tenants", { replace: true });
    } catch (e) {
      const ax = e as AxiosError<{ detail?: string }>;
      setError(ax.response?.data?.detail ?? "Invalid verification code");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box padding={{ vertical: "xxxl", horizontal: "l" }}>
      <div style={{ maxWidth: 420, margin: "0 auto" }}>
        <Container header={<Header variant="h1">Two-factor code</Header>}>
          <form onSubmit={submit}>
            <Form
              actions={
                <SpaceBetween direction="horizontal" size="xs">
                  <Button variant="primary" formAction="submit" loading={loading}>
                    Verify
                  </Button>
                </SpaceBetween>
              }
            >
              <SpaceBetween size="l">
                {error && <Alert type="error">{error}</Alert>}
                <FormField label="Authenticator code">
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.detail.value)}
                    autoFocus
                    inputMode="numeric"
                  />
                </FormField>
              </SpaceBetween>
            </Form>
          </form>
        </Container>
      </div>
    </Box>
  );
}
