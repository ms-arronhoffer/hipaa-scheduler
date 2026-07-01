# ePHI Inventory

Every place ePHI lives, moves, or gets logged. HIPAA §164.308(a)(1)(ii)(A)
requires the covered entity to know this — this document is our answer.
Update it in the same PR that introduces a new storage location, integration,
or export path.

## Storage at rest

| Location | Kind of ePHI | Encryption | Retention floor | Access controls |
| -------- | ------------ | ---------- | ---------------- | ---------------- |
| Postgres tables (all `patient*`, `appointment*`, `intake*`, `insurance*`, `document*`, `consent*`, `activity_log`) | Full patient record: demographics, MRN, appointments, intake responses, insurance, uploaded documents, PHI-tagged audit rows | Postgres TDE + LUKS on host volume | 6 years (HIPAA min) via `retention_service`; soft-delete keeps audit rows | Row-level filter by `org_id` in every query; RBAC guards in routers; `phi_log` writes an audit row on every access |
| Object storage (`S3_BUCKET`, `documents/` prefix) | Patient-uploaded consents, intake attachments, insurance card scans | Server-side AES256 (bucket policy); client-side age-encrypted for backups | 6 years | Signed URLs (short-lived); no public ACLs; VPC endpoint only |
| Object storage (`S3_BUCKET`, `backups/` prefix) | Full DB dumps | age-encrypted with maintainer-held recipient key; SSE-AES256 wrapper | 35 daily + 6 years of monthly | Key ownership limited to on-call ops; access logged to CloudTrail-equivalent |
| APScheduler job store (Postgres, `apscheduler_jobs` table) | Reminder job payloads — appointment IDs, NOT patient names | Same as Postgres | Purged when job fires or job is canceled | Same as Postgres |

## Storage NOT permitted

- **`localStorage` / browser `IndexedDB`** — banned; frontend `client.ts` uses
  `sessionStorage` only, and `frontend/src/api/__tests__/client.test.ts`
  asserts the invariant. XSS window is per-tab, not persistent.
- **Application logs** — structured logger deliberately does not accept
  patient identifiers as fields. Any log line containing an MRN, email, or
  UUID pattern in the `msg` string is a bug.
- **Sentry event bodies** — `before_send` runs `utils/phi_scrub.py` before
  the SDK ships anything.
- **URL query strings** — nginx access log format uses `$uri`, not
  `$request`; also asserted by comment in `nginx/nginx.conf`.

## In transit

| Path | Protocol | Notes |
| ---- | -------- | ----- |
| Browser ↔ nginx | TLS 1.2 or 1.3 (see `nginx.conf`) | HSTS `max-age=63072000; preload`; cert managed out of band (Let's Encrypt or provider-managed) |
| nginx ↔ backend / frontend containers | Plaintext on internal docker network | Acceptable only because the docker network is host-local; if backend is ever remoted, MUST switch to mTLS |
| Backend ↔ Postgres | TLS via asyncpg (`sslmode=require` in DATABASE_URL) | Enforced in production compose; local dev omits for developer ergonomics |
| Backend ↔ Twilio / SendGrid / Sentry / Google / MS | TLS 1.2+ (vendor-enforced) | BAA required per `baa-vendors.md` |
| Backend → Webhook subscribers | TLS 1.2+; HMAC-SHA256 signature required | Insecure `http://` subscriber URLs rejected in production mode |

## Rendered surfaces (UI)

| Surface | ePHI displayed | Access control |
| ------- | -------------- | -------------- |
| Staff frontend (`frontend/`) | Full patient record | JWT `aud=staff`; role-scoped routes; `require_mfa` for privileged roles when `org.mfa_required` |
| Patient portal (`patient-portal/`) | Only the signed-in patient's own record | JWT `aud=patient` (rejected by staff guards — see `test_jwt_audience.py`) |
| Admin frontend (`admin-frontend/`) | Cross-tenant metadata, NO patient records by default | `is_super_admin` required; PHI access via impersonation banner + audit row |
| Landing site (`landing/`) | None | Public; served on separate origin; no auth cookies |

## Egress paths (leaves our systems)

| Egress | Trigger | Contents | BAA? |
| ------ | ------- | -------- | ---- |
| Outbound email (SendGrid) | Reminder sweep, magic link, confirm/cancel token | Templates whitelist variables; PHI-scrubbing enforced at template render | Yes |
| Outbound SMS (Twilio) | Reminder sweep, opt-in prompt | ≤160 chars, appointment time + short link only; never patient full name | Yes |
| Outbound webhooks | Appointment/patient/intake/waitlist events | Envelope explicitly enumerated in `webhook_service.py`; HMAC signed | No (subscriber is the covered entity or a BA of theirs — their responsibility) |
| iCal export | Provider-initiated URL | Appointment times + type only (NOT patient name) unless the provider opts in per calendar | No (goes to the provider's own calendar app under their control) |
| Two-way calendar sync (Google/O365) | OAuth-connected provider | Appointment times + minimal patient identifier chosen by the provider (default: "Patient" placeholder; opt-in to name) | Yes (Google/MS BAA) |

## Contact / breach response

See `docs/hipaa/runbooks/incident-response.md`. tl;dr: incident commander is
on-call; §164.404 individual notice within 60 days; §164.408 HHS notice
depends on breach size.
