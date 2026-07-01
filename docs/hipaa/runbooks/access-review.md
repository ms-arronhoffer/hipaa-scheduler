# Access Review Runbook

Quarterly review of who has access to what. HIPAA §164.308(a)(3)(ii)(B)
requires "workforce clearance procedures" and §164.308(a)(4) requires
"information access management" — this runbook is our operational answer.

## Cadence

- **Quarterly** — full access review; every staff account, every API key,
  every super-admin.
- **On offboarding** — same day the person departs.
- **On role change** — within one business day.

## Quarterly review checklist

For each Organization in the system:

1. Export current staff list:
   ```sql
   SELECT id, email, roles, is_super_admin, last_login_at, locked_until, mfa_enabled
   FROM users WHERE org_id = :org_id AND deleted_at IS NULL
   ORDER BY last_login_at DESC NULLS LAST;
   ```
2. Send the export to the Practice Admin (Privacy Officer for that org).
   They confirm each row: "yes, still employed and needs this role" or
   "no, remove/downgrade".
3. Apply changes:
   - Downgrade roles via `/api/v1/users/{id}/roles` (staff UI)
   - Disable accounts via `/api/v1/users/{id}/disable`
   - Re-enable MFA if `mfa_enabled = false` on any privileged role
4. Log the review outcome in the org's ActivityLog by writing a
   `review_completed` event via the admin UI (leaves an audit trail).

For super-admin accounts (cross-tenant):

1. Export: `SELECT id, email, last_login_at FROM users WHERE is_super_admin = true`
2. Should be ≤ 3 people. If more, justify each additional one in the
   review doc.
3. Every super-admin MUST have MFA enrolled and an active `last_login_at`
   within the last 90 days. Otherwise disable.

For API keys (per-org):

1. Export: `SELECT id, short_prefix, scopes, last_used_at, created_by
   FROM api_keys WHERE org_id = :org_id AND revoked_at IS NULL`
2. Any key with `last_used_at IS NULL` and `created_at < 60 days ago` —
   revoke (unused, likely forgotten).
3. Any key not tied to a current employee (via `created_by`) — revoke.

## Offboarding checklist

Run same-day when a workforce member departs. In order:

1. **Disable the user account** (`users.deleted_at = now()`, or admin UI
   "Disable" button). This invalidates their JWT on next request.
2. **Force logout** — POST to `/api/v1/admin/users/{id}/revoke-sessions`.
   Rotates the user's refresh tokens.
3. **Revoke API keys they created** — query
   `SELECT id FROM api_keys WHERE created_by = :user_id AND revoked_at IS NULL`
   and revoke each.
4. **Un-share calendar sync** — if they had a Google/O365 OAuth connection,
   disconnect it via `/api/v1/calendar-sync/{id}/disconnect` so the refresh
   token stops being used.
5. **Review their activity for the last 30 days** — quick spot-check for
   unusual patterns before closing. Not a full forensic sweep unless
   there's a specific concern.
6. **Log the offboarding event** in ActivityLog by writing an
   `offboarded` action against the user's row.
7. **Document** in the covered entity's HR record that the technical
   revocation completed.

The user's ActivityLog rows STAY — 6-year retention still applies. They are
the evidence that access was legitimate while it existed.

## Role change

- If a role is being ADDED (broader access), require the Practice Admin's
  written approval before applying.
- If a role is being REMOVED (narrower access), apply immediately, then
  notify the Practice Admin.
- Every role change is an ActivityLog event — the `changes` JSONB has the
  before/after roles array.

## Break-glass (emergency access)

Sometimes a super-admin must access a practice's data outside of normal
support (e.g., PII deletion request when the Practice Admin is unreachable).

- Use the impersonation feature — never share credentials.
- Impersonation start writes an ActivityLog row and triggers an out-of-band
  alert to the Practice Admin (email + in-app).
- Impersonation session auto-expires after 60 minutes.
- Post-hoc: within one business day, write a break-glass justification note
  attached to the impersonation event (admin UI).

## Do NOT

- Do NOT skip the quarterly review because "nothing has changed" — the CE
  needs the attestation regardless. A one-line "confirmed no changes" from
  the Practice Admin satisfies the requirement.
- Do NOT hard-delete users. Soft-delete only, so the ActivityLog rows keep
  their `actor_id` foreign key intact.
- Do NOT share super-admin credentials — every human gets their own super-
  admin account. Shared credentials break the entire audit story.
