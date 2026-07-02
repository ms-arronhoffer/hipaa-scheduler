# Threat Model

Scope: the HIPAA-compliant multi-tenant scheduling application in this repo,
deployed via `docker-compose.yml` behind the nginx configuration in
`nginx/`, backed by managed Postgres 16 with TDE and encrypted object
storage.

We use STRIDE per component. Only threats with meaningful residual risk are
listed — controls that fully eliminate a threat are noted but not
re-analyzed.

## Trust boundaries

1. Public internet ↔ nginx (TLS termination, rate limits, security headers)
2. nginx ↔ backend (host-local docker network — plaintext acceptable *only*
   because the boundary does not leave the VM)
3. Backend ↔ Postgres (`sslmode=require` in production)
4. Backend ↔ external SaaS (Twilio, SendGrid, Sentry, S3, calendar OAuth) —
   TLS enforced, BAAs required per `baa-vendors.md`
5. Patient portal origin ↔ staff origin — cookie / storage isolation via
   separate subdomains; JWT audience separation (asserted by
   `test_jwt_audience.py`)

## Assets

- Patient ePHI (all fields in `Patient`, `IntakeSubmission`, `InsurancePolicy`,
  `Document`, `Appointment`, `ActivityLog`)
- Staff credentials (bcrypt hash + TOTP seed)
- API keys (sha256 hash only; plaintext never re-derivable)
- JWT signing key (`JWT_SECRET`)
- Backup encryption key (age recipient key)
- OAuth refresh tokens for calendar sync (encrypted at rest via
  application-layer `EncryptedString` keyed on the dedicated
  `PHI_ENCRYPTION_KEY`, independent of `JWT_SECRET`)

## Threats

### T1 — Cross-tenant data access via IDOR (S/E/I of STRIDE)

**Threat.** A staff user of Org A crafts a request against `/patients/{id}`
where `{id}` belongs to Org B.

**Controls.**
- Every query filters by `org_id` from the principal — enforced in the
  service layer, not just the router.
- `enforce_org_access` dependency compares `p.org_id` to any `org_id` path
  param and 403s on mismatch.
- Postgres row-level policies are NOT enabled today. Application-layer
  filtering is the only line of defense.

**Residual risk.** A missing `.where(Model.org_id == p.org_id)` clause in a
new query would leak. Mitigation: PR review checklist item, plus a
`pyright`-level custom rule (not yet built — tracked in `docs/hipaa/backlog.md`).

### T2 — Patient JWT used against staff endpoints (E/I)

**Threat.** A malicious patient reuses their `aud=patient` JWT against
`/api/v1/patients` (staff endpoint).

**Controls.**
- Staff and patient tokens share the same signing key but different
  `aud` claim. `decode(..., audience="staff")` raises
  `InvalidAudienceError` on a patient token.
- `test_jwt_audience.py` asserts this in both directions.

**Residual risk.** Low. A missing `audience=` arg on a `decode` call would
break the invariant — audit surface is small (2 call sites).

### T3 — Session hijack via XSS on staff origin (S/T/I)

**Threat.** A stored XSS in a patient name / intake response executes JS on
the staff calendar page, steals the access token, and calls the API as the
staff user.

**Controls.**
- Tokens live in `sessionStorage`, not `localStorage` (per-tab, cleared on
  tab close). Asserted by `frontend/src/api/__tests__/client.test.ts`.
- Nginx CSP `script-src 'self'` blocks inline / third-party JS.
- React auto-escapes text nodes; the only `dangerouslySetInnerHTML` in the
  codebase must go through PR-review scrutiny.
- Refresh tokens can be marked HttpOnly cookie (planned v1.2); today they
  are also in `sessionStorage`.

**Residual risk.** Medium — same-origin XSS still exfiltrates the access
token within the tab's lifetime. Move refresh token to HttpOnly SameSite=Strict
cookie in v1.2, keep access token in memory only.

### T4 — CSRF against state-changing staff endpoints (T)

**Threat.** A logged-in staff user visits a malicious site that POSTs to
`/api/v1/appointments`.

**Controls.**
- Auth is `Authorization: Bearer` header, NOT a cookie. Browsers do not
  auto-attach headers cross-origin, so CSRF against Bearer-auth APIs is
  structurally impossible.
- CORS is explicitly restrictive: only `FRONTEND_URL`, `ADMIN_URL`,
  `PATIENT_URL` origins allowed.

**Residual risk.** Reintroduced if we ever add a session cookie. Any cookie
auth MUST include SameSite=Lax minimum and a CSRF token.

### T5 — Webhook replay / forgery (S/T)

**Threat.** An attacker intercepts a webhook delivery and replays it against
the subscriber, or forges one to trigger downstream automation.

**Controls.**
- HMAC-SHA256 signature `t=<ts>,v1=<hex>` over `t.body`; subscriber verifies
  timestamp skew ≤ 5 min.
- `test_webhook_signing.py` asserts timestamp skew rejection and body
  tampering rejection.

**Residual risk.** Depends on subscriber's implementation. Ship a reference
verifier in `docs/hipaa/webhook-verifier-example.md`.

### T6 — Guest-booking flooding (D)

**Threat.** Someone scripts guest bookings to (a) burn provider slots and (b)
enumerate patient existence via duplicate email handling.

**Controls.**
- nginx `limit_req_zone` `pub=30r/m` on `/api/v1/pub/*` and `/patient-auth/*`.
- Public booking never confirms or denies patient existence — same 200
  response whether or not the email matches an existing PatientAccount.
- Slot reservation uses Postgres exclusion constraint — collisions return
  409, not 500, so replay is safe.

**Residual risk.** Distributed low-and-slow scraping. Mitigation: WAF /
Cloudflare in front of nginx for high-value tenants (post-v1).

### T7 — Backup theft (I)

**Threat.** Attacker gains read access to the S3 bucket housing DB dumps.

**Controls.**
- Backups are age-encrypted (`age -r <recipient>`) *before* upload; the
  bucket's SSE-AES256 is a second wrapper.
- Only the on-call ops role holds the age recipient private key. The
  hosting provider cannot decrypt.

**Residual risk.** Compromise of the age private key → full historical DB
disclosure. Mitigation: rotate age recipient annually; re-encrypt archive
tail in the same PR that rotates.

### T8 — Insider abuse / curious staff (I/R)

**Threat.** A staff user with legitimate access queries patient records they
have no business need to see (e.g., a celebrity, an ex-partner).

**Controls.**
- `phi_log` dependency writes an ActivityLog row on every PHI read — enforced
  at the router-dependency level, asserted by `test_phi_log_guard.py`.
- Admin frontend surfaces "PHI access log" per-patient and per-user views.
- 6-year retention on ActivityLog rows via `retention_service`.

**Residual risk.** Detection, not prevention. Practices should periodically
review the access log — this is a documented operational responsibility of
the covered entity, not something the software can enforce.

### T9 — Impersonation-with-banner abuse (R/E)

**Threat.** A super-admin uses the impersonation feature to act as a
practice user, reads PHI, then denies it.

**Controls.**
- Impersonation start + stop are ActivityLog events with `actor_type=super_admin`
  and `impersonated_user_id` in `changes`.
- The staff UI shows a persistent red banner during impersonation (asserted
  visually — no automated test yet).
- Every PHI access during impersonation is logged with the impersonator's ID
  as `actor_id`, not the target user's.

**Residual risk.** UI banner could be evaded via API-only impersonation
(bypasses the staff SPA entirely). Mitigation: log an out-of-band alert to
the impersonated tenant's admin on every impersonation session start.

### T10 — Dependency compromise (T/E)

**Threat.** A malicious `pip` / `npm` package pulled by CI runs during
build and steals `JWT_SECRET` or bakes a backdoor into the image.

**Controls.**
- `pip-audit` and `npm audit` in CI (blocking on high/critical).
- `bandit` and ZAP baseline in CI.
- Production images should be rebuilt from source in the covered entity's
  own registry, not pulled from public Docker Hub.

**Residual risk.** Zero-day supply-chain compromise before advisories exist.
Mitigation: pin exact versions (`==`, not `>=`) in `requirements.txt` and
`package-lock.json`; require hash-verified installs for production
(`pip install --require-hashes`).

## Out of scope

- Physical security of the hosting provider's data center (covered by the
  provider's own attestations + BAA).
- Endpoint security of practice staff workstations (covered entity's
  responsibility — recommend Rippling / Kandji / equivalent MDM).
- DDoS at the network layer (put Cloudflare or provider WAF in front of
  nginx for production; not part of this repo's config).

## Review cadence

Threat model is revisited each minor version (v1.1, v1.2, ...). Every new
router or new SaaS dependency triggers a spot-review of the relevant
sections — call it out in the PR description under **Security Impact**.
