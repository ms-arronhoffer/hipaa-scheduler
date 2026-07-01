# Business Associate Agreements — Vendor Register

Every vendor that stores, processes, or transmits ePHI on behalf of a covered
entity that uses this application MUST have a signed, current BAA on file with
the covered entity. This document is the **operational** register — the source
of truth for which vendors are approved, what data reaches them, and where the
BAA is filed.

The covered entity signs the BAA. This project's maintainer is a Business
Associate to the covered entity and a subcontractor to each vendor below.

## Contract

Adding a new SaaS dependency that will touch ePHI is a **security-review-required
change**. The reviewer must:

1. Confirm the vendor offers a HIPAA BAA (not just a "we're SOC 2" claim).
2. File the countersigned BAA under `docs/hipaa/baas/<vendor>-<yyyy-mm-dd>.pdf`
   (gitignored — store in the covered entity's document vault, not the repo).
3. Add a row to the register below, including the **BAA-covered data** column
   (be specific — "patient email" is not the same as "patient full record").
4. Update `docs/hipaa/ephi-inventory.md` if the vendor introduces a new place
   where ePHI is stored or transmitted.

## Register (v1.0 baseline)

| Vendor            | Purpose                         | BAA required? | Data covered by BAA                            | BAA on file? |
| ----------------- | ------------------------------- | ------------- | ---------------------------------------------- | ------------ |
| Twilio            | SMS reminders, inbound STOP/YES | **Yes**       | Patient mobile number, appointment metadata    | REQUIRED before enabling `TWILIO_*` env |
| SendGrid          | Email reminders, magic links    | **Yes**       | Patient email, appointment metadata            | REQUIRED before enabling `SENDGRID_API_KEY` |
| Sentry            | Error monitoring                | **Yes**       | Stack traces (PHI scrubbed by `before_send`)   | REQUIRED before enabling `SENTRY_DSN` |
| Hosting provider  | VM / managed Postgres           | **Yes**       | Full database (all ePHI at rest and in transit)| REQUIRED before production go-live |
| Object storage    | Encrypted backups + documents   | **Yes**       | Encrypted backup blobs, patient documents      | REQUIRED before enabling `S3_*` env |
| Google Workspace  | OAuth for two-way calendar sync | **Yes**       | Appointment times + patient name (calendar events) | REQUIRED before enabling `GOOGLE_OAUTH_*` |
| Microsoft 365     | OAuth for two-way calendar sync | **Yes**       | Appointment times + patient name (calendar events) | REQUIRED before enabling `MS_OAUTH_*` |

Vendors we deliberately DO NOT use (BAA-adjacent risk):

- **Stripe / payment processors** — no billing in v1; if added, PCI + BAA path
  must both be worked before wiring.
- **Public error trackers without BAA** — Rollbar, Bugsnag free tier, etc.
- **Public analytics** — no third-party JS on any authenticated origin.
  Landing page only.

## Enforcement

- CI blocks a merge that adds a new SDK to `backend/requirements.txt` or
  `*/package.json` if it touches network egress and is not in the register.
  (Manual review today; ratchet toward `pip-audit --require-hashes` +
  allowlist later.)
- Production `docker-compose.yml` refuses to boot if a service is configured
  (env var present) but the corresponding register row is not marked
  "on file" via the `BAA_VENDORS_ATTESTED` env var (comma-separated list).
- On BAA expiration or termination, disable the corresponding env var
  first, THEN notify the vendor. Do not risk continued ePHI transmission
  during renegotiation.
