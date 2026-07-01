import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AxiosError } from "axios";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import Input from "@cloudscape-design/components/input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Alert from "@cloudscape-design/components/alert";
import { authApi } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export default function LoginPage() {
  const nav = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const from = (location.state as { from?: string } | null)?.from ?? "/dashboard";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.login(email, password);
      if (res.mfa_required && res.mfa_ticket) {
        nav("/mfa", { state: { ticket: res.mfa_ticket, from } });
        return;
      }
      if (!res.access_token) {
        setError("Unexpected login response");
        return;
      }
      await login(res.access_token, res.refresh_token);
      nav(from, { replace: true });
    } catch (e) {
      const ax = e as AxiosError<{ detail?: string }>;
      setError(ax.response?.data?.detail ?? "Invalid email or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Box padding={{ vertical: "xxxl", horizontal: "l" }}>
      <div style={{ maxWidth: 420, margin: "0 auto" }}>
        <Container header={<Header variant="h1">Sign in</Header>}>
          <form onSubmit={submit}>
            <Form
              actions={
                <SpaceBetween direction="horizontal" size="xs">
                  <Button variant="primary" formAction="submit" loading={loading}>
                    Sign in
                  </Button>
                </SpaceBetween>
              }
            >
              <SpaceBetween size="l">
                {error && <Alert type="error">{error}</Alert>}
                <FormField label="Email">
                  <Input
                    value={email}
                    onChange={(e) => setEmail(e.detail.value)}
                    type="email"
                    autoFocus
                    placeholder="you@practice.com"
                  />
                </FormField>
                <FormField label="Password">
                  <Input
                    value={password}
                    onChange={(e) => setPassword(e.detail.value)}
                    type="password"
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
