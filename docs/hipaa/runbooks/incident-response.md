# Incident Response Runbook

Use this when you suspect or confirm an ePHI incident: unauthorized access,
loss, disclosure, or a security event that MAY have exposed ePHI. Err on
the side of running the playbook — a 30-minute investigation that ends in
"no ePHI touched" is much cheaper than a missed §164.404 clock.

## Roles

- **Incident Commander (IC)** — the person who declares the incident. Drives
  the timeline, owns communication, decides when to close. Default: the
  senior engineer on the on-call rotation.
- **Scribe** — records every action, timestamp, and observation to the
  incident channel or shared doc. Same person as IC only if nobody else is
  available.
- **Covered Entity Contact** — the practice's designated Privacy Officer.
  Contact list lives in `docs/hipaa/contacts.md` (gitignored — sits in the
  ops vault).

## Severity

| Level | Definition | Response time |
| ----- | ---------- | ------------- |
| SEV1 | Confirmed ePHI disclosure to unauthorized party OR active exploitation | IC engaged ≤ 15 min; Privacy Officer notified ≤ 1 hr |
| SEV2 | Suspected ePHI disclosure OR active vulnerability with no confirmed exposure | IC engaged ≤ 1 hr; Privacy Officer notified ≤ 4 hr |
| SEV3 | Security event with no ePHI implication (e.g. brute force blocked at the WAF) | IC engaged next business day; documented, no external notice |

## Immediate actions (first 30 min)

1. **Declare.** Open an incident channel; assign IC + scribe. Post SEV level.
2. **Preserve evidence.** Do NOT restart affected services. Snapshot:
   - `docker compose logs --no-color --tail=10000 > incident-<ts>-logs.txt`
   - `docker compose exec postgres pg_dump ... > incident-<ts>-db.sql.gz`
     (encrypt with age before storing)
   - nginx access log for the affected window (already excludes PHI —
     see `nginx.conf`)
3. **Contain.** Choose the minimum action that halts further exposure:
   - Suspected credential compromise → rotate `JWT_SECRET` (all sessions
     invalidated) OR force logout the specific user via the admin UI.
   - Suspected API key compromise → revoke via `/api/v1/api-keys/{id}` and
     query `activity_log` for prior use.
   - Active exploitation in progress → put nginx in maintenance mode
     (`docker compose exec nginx nginx -s reload` after swapping in
     `nginx/conf.d/maintenance.conf.template`).
4. **Scope.** Query `activity_log` for the window:
   ```sql
   SELECT actor_id, actor_email, entity_type, entity_id, action, ip, created_at
   FROM activity_log
   WHERE created_at BETWEEN :start AND :end
     AND (phi_accessed = true OR actor_id = :suspect)
   ORDER BY created_at;
   ```
   Save the result — this is the basis for §164.404 individual notice
   determination.

## §164.404 notification obligation

The covered entity (the practice), not this application, has the direct
notification obligation. **Our job is to give the Privacy Officer the facts
they need within 24 hours of confirmation.**

- **Individual notice**: within 60 days of discovery. §164.404(a)(1).
  Includes the individuals' identities, a description of ePHI involved,
  what happened, mitigation steps, and the CE's contact info.
- **HHS notice**: within 60 days if ≥ 500 affected; annually otherwise.
  §164.408.
- **Media notice**: within 60 days if ≥ 500 residents of a state/jurisdiction.
  §164.406.

Hand the scoped audit-log extract + the ePHI inventory
(`docs/hipaa/ephi-inventory.md`) to the Privacy Officer as the evidence
package. Do not draft the notice yourself — that is the CE's counsel.

## Recovery

1. **Root cause.** Write it in the incident doc BEFORE closing. No "human
   error" — that's not a root cause. What was the missing control?
2. **Rotate.** Any secret that touched the incident:
   - `JWT_SECRET` — all users signed out; refresh tokens invalidated
   - Age backup recipient key (if T7-class incident) — re-encrypt archive
   - Any API key surfaced in logs
3. **Patch.** File the fix as a PR referencing this incident by ID.
4. **Backfill test.** The bug that let this happen becomes a regression
   test. No test = incident is not closed.
5. **Post-mortem.** Blameless, within 5 business days. Distribute to
   engineering + Privacy Officer.

## Common patterns

### Suspected staff credential compromise

- Force logout via admin UI (invalidates the user's refresh tokens)
- Reset password + require MFA re-enrollment
- Query `activity_log WHERE actor_id = :user AND created_at > :when`
  — look for volume anomalies or unusual entity types
- If MFA was NOT enabled: enable it org-wide via `org.mfa_required`, then
  investigate why it wasn't required (v1 default is `true` — this is a
  config drift bug)

### Suspected API key compromise

- Revoke via `POST /api/v1/api-keys/{id}/revoke`
- The plaintext key is not recoverable (only sha256 is stored) — the
  practice must issue a new one to the integration owner
- Query `activity_log WHERE actor_type='api_key' AND actor_id = :key_id`

### Suspected data-at-rest access (backup or DB dump leak)

- SEV1 by default — assume worst case until scoped
- Rotate DB encryption key at the provider (this triggers a re-encrypt
  cycle — coordinate downtime)
- Rotate age recipient key; re-encrypt archived backups in the same batch
- Scope = every record present in the leaked snapshot

## Do NOT

- Do NOT delete logs, dump files, or evidence — even embarrassing ones.
- Do NOT communicate details to affected individuals directly. That's the
  CE's role and requires their counsel's language.
- Do NOT restart services before capturing logs unless containment
  requires it (and if it does, capture what you can first).
- Do NOT close the incident until root cause is documented AND a
  regression test exists.
