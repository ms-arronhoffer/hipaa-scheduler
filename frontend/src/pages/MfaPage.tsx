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
  const { state } = useLocation();
  const { login } = useAuth();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const ticket = (state as { ticket?: string } | null)?.ticket;
  const from = (state as { from?: string } | null)?.from ?? "/dashboard";

  if (!ticket) {
    nav("/login", { replace: true });
    return null;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.verifyMfa(ticket!, code);
      if (!res.access_token) {
        setError("Invalid code");
        return;
      }
      await login(res.access_token, res.refresh_token);
      nav(from, { replace: true });
    } catch (e) {
      const ax = e as AxiosError<{ detail?: string }>;
      setError(ax.response?.data?.detail ?? "Invalid code");
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
                <Button variant="primary" formAction="submit" loading={loading}>
                  Verify
                </Button>
              }
            >
              <SpaceBetween size="l">
                {error && <Alert type="error">{error}</Alert>}
                <FormField label="6-digit code" description="From your authenticator app">
                  <Input
                    value={code}
                    onChange={(e) => setCode(e.detail.value.replace(/\D/g, "").slice(0, 6))}
                    inputMode="numeric"
                    autoFocus
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
