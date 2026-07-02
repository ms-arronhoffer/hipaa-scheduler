# End-to-End Verification Checklist

Follow this once, top to bottom, before declaring v1 ready to ship to a
covered entity. Every step has an expected observation; a mismatch is a
release blocker.

Assumes: docker + docker compose installed, `mkcert` available (or your
own local CA), age installed, awscli configured with the backup bucket's
credentials.

---

## 0. Prerequisites

- [ ] Clone repo; `cd hipaa-scheduler`
- [ ] `cp .env.example .env` and fill in every `${VAR:?required}` value.
      For local verification, put dev values — this file must NEVER be
      committed.
- [ ] `cd nginx/certs && mkcert localhost admin.localhost portal.localhost`
      → produces `.pem`+`.key` files. Rename to
      `staff.crt` / `staff.key`, etc. per `nginx/certs/README.md`.

## 1. Backend static checks

- [ ] `python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"`
      → exits 0 (**observed OK**)
- [ ] `python -m py_compile $(git ls-files 'backend/app/*.py')`
      → exits 0 (**observed OK — full syntax scan clean**)
- [ ] Optional: `docker compose -f docker-compose_local.yml config` → prints
      the merged config with no warnings.

## 2. Bring up the local stack

- [ ] `docker compose -f docker-compose_local.yml up -d`
- [ ] `docker compose ps` — every service `Up (healthy)` within 60s.
- [ ] `curl -sfk https://localhost/api/v1/readyz` → 200 with JSON
      `{"database":"ok","scheduler":"ok"}`
- [ ] `docker compose logs backend --tail=50` — no ERROR lines, and
      no line contains an email address, UUID, or the string "patient"
      followed by an identifier (PHI-in-log invariant).

## 3. Migration + seed

- [ ] `docker compose exec backend alembic upgrade head` → runs `001_initial`.
- [ ] Assert the exclusion constraint exists:
      ```
      docker compose exec postgres psql -U hs_admin -d hipaa_scheduler -c \
        "SELECT conname FROM pg_constraint WHERE contype='x' AND conrelid='appointment'::regclass;"
      ```
      → returns at least one row (the tstzrange GiST exclusion).
- [ ] `docker compose exec backend python -m app.seed.seed_e2e` → creates
      one Org, one Office, one Provider, one AppointmentType with
      `public_bookable=true`, and one availability window in the next 7d.

## 4. JWT audience separation (security)

- [ ] `docker compose exec backend pytest tests/test_jwt_audience.py -q`
      → all pass. Confirms `test_patient_token_rejected_by_staff_audience`
      raises `InvalidAudienceError`.

## 5. Audit-log invariant

- [ ] `docker compose exec backend pytest tests/test_phi_log_guard.py -q`
      → all pass.
- [ ] Manual: log in as staff, open a patient record, then
      ```
      docker compose exec postgres psql -U hs_admin -d hipaa_scheduler -c \
        "SELECT actor_email, entity_type, action, phi_accessed
           FROM activity_log WHERE phi_accessed=true ORDER BY created_at DESC LIMIT 5;"
      ```
      → the read shows up with `phi_accessed=true`.

## 6. Full unit test suite

- [ ] `docker compose exec backend pytest -q`
      → all unit tests pass. Integration tests are skipped without
      `-m integration` (by design — see `conftest.py`).

## 7. Frontend tests

- [ ] `cd frontend && npm ci && npm run test:run` → Vitest suite green.
      Includes token-storage XSS invariant
      (`client.test.ts`: "does NOT use localStorage").
- [ ] `cd admin-frontend && npm ci && npm run build` → clean build.
- [ ] `cd patient-portal && npm ci && npm run build` → clean build.

## 8. Golden-path booking (manual)

- [ ] Staff: open `https://localhost/`, log in as seeded admin, create an
      appointment for a seeded patient → renders in the calendar; cancel
      it → status flips to canceled.
- [ ] Patient portal: open `https://portal.localhost/`, request magic link
      for the seeded patient's email → email lands in Mailhog (`http://localhost:8025`)
      → click link → land in portal; book an appointment → confirmation
      renders WITHOUT any UUID visible in body copy.
- [ ] Guest: open portal in incognito, book without magic link → same
      confirmation surface.
- [ ] Cancel a booking that has a matching waitlist entry → worker fires
      the auto-fill; verify with:
      `docker compose logs worker | grep waitlist_fill`.

## 9. Webhook delivery + HMAC

- [ ] Create a WebhookSubscription pointing at `http://mailhog:8025/api/v2/messages`
      (any reflector) with events `[appointment.created]`.
- [ ] Create an appointment; poll:
      `SELECT status, attempts, signature FROM webhook_delivery
         ORDER BY created_at DESC LIMIT 1;`
      → `status='delivered'`, `signature` starts with `t=`.
- [ ] Manually verify HMAC in a REPL using the subscription's secret and
      the recorded body — must match the `v1=` component of the signature.

## 10. Reminder sweep

- [ ] Create an appointment 1440 minutes out with a template that references
      only allowed variables (no patient name in subject).
- [ ] `docker compose exec worker python -m app.tasks.reminder_sweep --force-now`
      (or wait 5 min for the scheduled fire) → message arrives in Mailhog.
- [ ] Inspect the email body — no MRN, no full DOB, no diagnosis. Only
      appointment time + short link (`/api/v1/confirm/{token}`).

## 11. nginx security headers

For each of the three server_names, run:
```
curl -skI https://localhost/         | grep -Ei 'strict-transport|content-security-policy|x-frame|referrer-policy|permissions-policy'
curl -skI https://admin.localhost/   | grep -Ei 'strict-transport|content-security-policy|x-frame|referrer-policy|permissions-policy'
curl -skI https://portal.localhost/  | grep -Ei 'strict-transport|content-security-policy|x-frame|referrer-policy|permissions-policy'
```
- [ ] Every response includes: `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`
- [ ] Every response includes a `Content-Security-Policy` header
- [ ] Every response includes `X-Frame-Options: DENY`
- [ ] Every response includes `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] `curl -sk http://localhost/` → 301 redirect to `https://localhost/`

## 12. PHI-safe access logs

- [ ] Hit `https://localhost/api/v1/patients/00000000-0000-0000-0000-000000000001?mrn=A123`
- [ ] `docker compose logs nginx --tail=5` — the log line contains
      `/api/v1/patients/00000000...` (from `$uri`) but MUST NOT contain
      `mrn=A123` (would be in `$request`, which we deliberately did not
      use). This is the smoke test for the PHI-safe log format.

## 13. Backup + restore drill

- [ ] `./backup.sh` → prints "Uploaded s3://.../daily/<date>.sql.gz.age"
- [ ] `aws s3 ls s3://$BACKUP_S3_BUCKET/$BACKUP_S3_PREFIX/daily/` → object
      present, size > 0.
- [ ] Follow `docs/hipaa/runbooks/backup-restore.md` §"Test restore" against
      a scratch Postgres → row counts match production.
- [ ] Log the drill in `docs/hipaa/audit-log.md` (gitignored operations log).

## 14. API key auth

- [ ] Create an API key via `/api/v1/api-keys` → response includes the
      plaintext `hs_...` value ONCE.
- [ ] `curl -sk -H "Authorization: Bearer hs_..." https://localhost/api/v1/appointments`
      → 200.
- [ ] `curl -sk https://localhost/api/v1/appointments` → 401.
- [ ] `SELECT sha256_hash FROM api_keys WHERE id=...` — the stored value
      is sha256, NOT the plaintext.

## 15. HIPAA docs review

- [ ] `docs/hipaa/README.md` exists and links to every subdocument.
- [ ] `docs/hipaa/baa-vendors.md` lists every enabled integration.
- [ ] `docs/hipaa/ephi-inventory.md` covers every table containing PHI.
- [ ] `docs/hipaa/threat-model.md` — every T# has controls + residual risk.
- [ ] All three runbooks exist: incident-response, backup-restore, access-review.

## 16. Sign-off

- [ ] All checkboxes above are checked.
- [ ] Any red flags escalated per `docs/hipaa/runbooks/incident-response.md`.
- [ ] Release notes drafted mentioning the v1 scope from the plan
      (multi-tenant, PHI, three-mode patient auth, integrations).
- [ ] Ship.

---

## What is intentionally NOT in this checklist

- **Load / stress testing.** Not a pass/fail gate for v1, but a Locust profile
  now exists (`backend/tests/load/`, run manually) to establish guest-booking
  capacity — see `docs/hipaa/backlog.md`.
- **Full accessibility audit.** Cloudscape gives us WCAG 2.1 AA baseline;
  a full audit is post-v1.
- **Cross-browser matrix beyond Chromium + Firefox.** Safari + Edge before v1.1.
- **DR failover.** Requires two hosting regions; v1 ships single-region.
