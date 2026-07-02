# HIPAA Scheduler

Multi-tenant HIPAA-compliant scheduling SaaS for chiropractor and dentist offices.

- **Backend**: FastAPI async + SQLAlchemy 2.0 + Alembic + Postgres 16
- **Staff frontend**: React 18 + TypeScript + Vite + Cloudscape Design System (port 4000)
- **Admin frontend**: React 18 + TS + Vite (super-admin, port 4001)
- **Patient portal**: React 18 + TS + Vite (public booking + magic-link + intake, port 4002)
- **Nginx**: TLS termination + HSTS + CSP + security headers
- **Deployment**: Docker Compose on HIPAA-compliant VM

## Quick start (local)

```bash
cp .env.example .env
docker compose -f docker-compose_local.yml up -d
```

- Staff frontend: https://localhost/
- Admin: https://localhost:4001/
- Patient portal: https://localhost:4002/
- Backend API: https://localhost/api/v1/
- Health: https://localhost/api/v1/readyz

### First login

On first boot the backend applies migrations and **bootstraps a super-admin**
from `DEFAULT_ADMIN_EMAIL` / `DEFAULT_ADMIN_PASSWORD` (see `app/bootstrap.py`).
Log in to the admin portal with those credentials, then provision tenants and
practice-admins from there. The bootstrap is idempotent and never overwrites an
existing account's password, so rotate the seed password after first login.
Additional platform operators can be pre-authorized by listing their emails in
`SUPER_ADMIN_EMAILS`; matching users are promoted to super-admin on startup.

## HIPAA controls

- Every PHI access logged to `ActivityLog` with `phi_accessed=true` (see `docs/hipaa/ephi-inventory.md`)
- 6-year audit retention floor enforced in `services/retention_service.py`
- MFA required for privileged staff roles when `org.mfa_required=true`
- TLS 1.2+, HSTS, CSP; no PHI in query strings; PHI scrubbed from Sentry
- Postgres TDE + volume LUKS; nightly encrypted backups
- BAA vendors documented in `docs/hipaa/baa-vendors.md`

## Phased delivery

- **v1.0 (MVP, current)**: Orgs, Users, RBAC, MFA, Patients, AppointmentTypes, Providers, Availability, Appointments, staff calendar, email reminders, ActivityLog, ApiKeys, basic reports
- **v1.1**: Patient portal (magic-link + full account), public booking, SMS + opt-in, intake form builder, waitlist, cancellation policy
- **v1.2**: Recurring RRULE, resources/rooms, webhooks + retries, iCal export, guest-claim flow
- **v1.3**: Two-way calendar sync (Google/O365), advanced reports, super-admin cross-tenant audit search, documents + consents
