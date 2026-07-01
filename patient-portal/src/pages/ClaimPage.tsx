import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Alert from "@cloudscape-design/components/alert";
import Box from "@cloudscape-design/components/box";
import Spinner from "@cloudscape-design/components/spinner";
import { patientAuthApi } from "../api/patientAuth";
import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/layout/PageHeader";

export default function ClaimPage() {
  const { token = "" } = useParams();
  const nav = useNavigate();
  const { loginWithToken } = useAuth();
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await patientAuthApi.claim(token);
        if (!mounted) return;
        loginWithToken(res.access_token);
        nav("/me/appointments", { replace: true });
      } catch {
        if (mounted) setErr("This claim link is invalid or has expired.");
      }
    })();
    return () => {
      mounted = false;
    };
  }, [token, loginWithToken, nav]);

  if (err) {
    return (
      <PageHeader title="Claim failed">
        <Alert type="error">{err}</Alert>
      </PageHeader>
    );
  }
  return (
    <Box textAlign="center" padding="xxl">
      <Spinner size="large" />
    </Box>
  );
}
