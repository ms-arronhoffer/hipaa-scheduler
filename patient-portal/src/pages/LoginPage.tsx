import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Form from "@cloudscape-design/components/form";
import FormField from "@cloudscape-design/components/form-field";
import Input from "@cloudscape-design/components/input";
import SegmentedControl from "@cloudscape-design/components/segmented-control";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { patientAuthApi } from "../api/patientAuth";
import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/layout/PageHeader";

type Mode = "magic" | "password";

export default function LoginPage() {
  const nav = useNavigate();
  const { loginWithToken } = useAuth();
  const [mode, setMode] = useState<Mode>("magic");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [magicSent, setMagicSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!email) return;
    setBusy(true);
    setErr(null);
    try {
      if (mode === "magic") {
        await patientAuthApi.requestMagic(email);
        setMagicSent(true);
      } else {
        const res = await patientAuthApi.login(email, password);
        loginWithToken(res.access_token);
        nav("/me/appointments");
      }
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      setErr(err.response?.data?.detail ?? "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  if (magicSent) {
    return (
      <PageHeader title="Check your email">
        <Alert type="success">
          If an account exists for {email}, we've sent a sign-in link. It will expire in
          15 minutes.
        </Alert>
      </PageHeader>
    );
  }

  return (
    <PageHeader title="Sign in" description="Access your appointments and intake forms.">
      <form onSubmit={submit}>
        <Form
          actions={
            <Button
              variant="primary"
              loading={busy}
              disabled={!email || (mode === "password" && !password)}
              onClick={() => void submit(new Event("submit") as unknown as FormEvent)}
            >
              {mode === "magic" ? "Email me a link" : "Sign in"}
            </Button>
          }
        >
          <SpaceBetween size="m">
            {err && <Alert type="error">{err}</Alert>}
            <Box>
              <SegmentedControl
                selectedId={mode}
                onChange={(e) => setMode(e.detail.selectedId as Mode)}
                options={[
                  { id: "magic", text: "Email link" },
                  { id: "password", text: "Password" },
                ]}
              />
            </Box>
            <FormField label="Email">
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.detail.value)}
                autoFocus
              />
            </FormField>
            {mode === "password" && (
              <FormField label="Password">
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.detail.value)}
                />
              </FormField>
            )}
          </SpaceBetween>
        </Form>
      </form>
    </PageHeader>
  );
}
