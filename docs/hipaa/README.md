# HIPAA Compliance Documentation

Operational documents for HIPAA compliance of the scheduling application in
this repo. These are living documents — update them in the same PR that
changes the underlying system behavior.

## Index

- **[baa-vendors.md](baa-vendors.md)** — Register of every vendor that
  touches ePHI, with BAA-on-file status. Blocks enabling any integration
  without a corresponding BAA row.
- **[ephi-inventory.md](ephi-inventory.md)** — Every place ePHI lives,
  moves, or gets displayed. Required by §164.308(a)(1)(ii)(A).
- **[threat-model.md](threat-model.md)** — STRIDE model with controls
  and residual risks. Reviewed every minor version.
- **[backlog.md](backlog.md)** — Tracked security/HIPAA follow-up work:
  encryption of indexed PHI (deferred, with decision), the IDOR static check,
  and load testing (both delivered).
- **runbooks/**
  - **[incident-response.md](runbooks/incident-response.md)** — What to
    do when an incident is declared. §164.404 notification obligations.
  - **[backup-restore.md](runbooks/backup-restore.md)** — Nightly backup
    verification and quarterly restore drill. RPO 24h, RTO 4h.
  - **[access-review.md](runbooks/access-review.md)** — Quarterly access
    review and same-day offboarding. §164.308(a)(3)–(4).

## Not in this repo (by design)

- **Signed BAAs** — filed in the covered entity's document vault, not the
  code repo. See baa-vendors.md for filing convention.
- **Contact list** (Privacy Officer, on-call rotation) — lives in the ops
  vault. `docs/hipaa/contacts.md` is gitignored.
- **Notice of Privacy Practices** — the covered entity's document, not
  this application's.
- **Risk analysis** — the covered entity's obligation under §164.308(a)(1)(ii)(A).
  Our threat-model.md is an input, not a substitute.

## Compliance posture

This application is designed to help a covered entity meet HIPAA. It does
not, by itself, make anyone HIPAA-compliant. The covered entity is
responsible for:

- Signing BAAs with vendors before enabling those integrations
- Configuring practices' access policies and running access reviews
- Notifying individuals + HHS on breach
- Their own risk analysis and workforce training
- Physical + endpoint security of workforce workstations

We are responsible for:

- The technical controls documented here operating as described
- Encryption of ePHI at rest and in transit inside our system boundaries
- Audit logging of PHI access
- Timely disclosure to the covered entity when we suspect an incident
