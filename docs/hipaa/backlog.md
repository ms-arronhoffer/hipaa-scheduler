# Security & HIPAA Backlog

Tracked, non-blocking follow-up work referenced from `threat-model.md` and
`verification-checklist.md`. Items here are deliberately deferred out of a
release for scope or design reasons — each says *why* and *what the approach is*
so the next person does not have to re-derive it.

## Encryption at rest (ePHI)

Application-layer encryption landed in **P2** (`app/utils/crypto.py`,
`app/models/types.py::EncryptedString`, migration `0002_encrypt_phi_at_rest`).
That first increment covers **free-text / non-indexed** ePHI only:

- `appointments.notes`
- `insurance_policies.member_id`, `insurance_policies.group_number`
- `calendar_connections.access_token_ct` / `refresh_token_ct` (wires the
  previously-aspirational "encrypted at rest" claim to a real implementation)

### Deferred: indexed / unique PHI columns

The following columns are **still plaintext** because encrypting them naively
would break the equality lookups, unique constraints, or range queries they
participate in. They need a *blind index* (deterministic keyed HMAC stored in a
sidecar column) or an equivalent searchable-encryption design before they can
be encrypted:

| Column | Blocker | Sketch of approach |
| --- | --- | --- |
| `patients.email` | indexed; used for exact-match lookup | store `email_bidx = HMAC-SHA256(key, normalized_email)`; query on the blind index, keep ciphertext in `email` |
| `patients.mrn` | `uq_patients_org_mrn` unique constraint | unique blind index on `(org_id, mrn_bidx)`; ciphertext in `mrn` |
| `patients.last_name` | `ix_patients_org_lastname` (prefix/sort search) | hardest case — deterministic blind index only supports exact match, not prefix/sort. Options: encrypted + separate search service, or accept plaintext with compensating controls. Decide explicitly. |
| `patients.dob` | `ix_patients_org_dob` (range/exact) | blind index for exact match; range search needs order-preserving scheme or plaintext-with-controls |
| `patient_accounts.totp_secret` | read on every MFA verify | straightforward `EncryptedString` swap — no index; deferred only to keep P2 scope tight. Low effort, do next. |

**Key management for blind indexes.** The HMAC key must be *separate* from
`PHI_ENCRYPTION_KEY` (a leak of one must not weaken the other) and must be
rotatable — rotating it requires recomputing every blind index, so version the
blind-index column the same way ciphertext is versioned.

## Cross-tenant IDOR static analysis (from threat-model T1)

`threat-model.md` §T1 notes the residual risk of a new query missing its
`.where(Model.org_id == p.org_id)` clause. Planned mitigation: a `pyright`-level
or custom-lint rule that flags `select(<OrgScoped model>)` without an `org_id`
predicate. Not yet built.

## Load / stress testing (from verification-checklist §"NOT in this checklist")

Locust profile against `/api/v1/pub/availability` to establish capacity limits
for guest booking. Planned, not blocking for v1.
