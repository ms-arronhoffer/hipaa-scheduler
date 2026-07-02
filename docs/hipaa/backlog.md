# Security & HIPAA Backlog

Tracked follow-up security/HIPAA work referenced from `threat-model.md` and
`verification-checklist.md`. Each item says *why* and *what the approach is* so
the next person does not have to re-derive it. Items completed in a later
increment are marked **done** inline (with the delivering migration/tooling)
rather than deleted, so the history of *why* stays readable.

## Encryption at rest (ePHI)

Application-layer encryption landed in **P2** (`app/utils/crypto.py`,
`app/models/types.py::EncryptedString`, migration `0002_encrypt_phi_at_rest`).
That first increment covers **free-text / non-indexed** ePHI only:

- `appointments.notes`
- `insurance_policies.member_id`, `insurance_policies.group_number`
- `calendar_connections.access_token_ct` / `refresh_token_ct` (wires the
  previously-aspirational "encrypted at rest" claim to a real implementation)

**P3** extended `EncryptedString` to the MFA shared secrets (migration
`0003_encrypt_totp_secret`) — these are non-indexed and read on every MFA
verify, so no blind-index design was needed:

- `users.totp_secret` (staff MFA) — **done**
- `patient_accounts.totp_secret` (patient-portal MFA) — **done**

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

**Decision (P3).** These four columns stay **plaintext for now, with
compensating controls**, and are *not* attempted in this increment. They are
not independent: the staff patient-search endpoint
(`app/routers/patients.py::list_patients`) filters `email`, `mrn`,
`first_name`, and `last_name` together with substring `ILIKE` **and** orders by
`last_name`/`first_name`. A deterministic blind index only answers exact-match
lookups, so it cannot serve that substring-search + sort UX for any of these
columns. Encrypting them therefore requires either a dedicated
searchable-encryption scheme or an external search service — a project in its
own right, out of scope for P3. Compensating controls in the meantime: strict
app-layer tenant isolation (see IDOR check below), disk/TDE-level encryption,
audit logging of PHI access (`phi_log`), and least-privilege DB roles.

**Key management for blind indexes.** When the above is implemented, the HMAC
key must be *separate* from `PHI_ENCRYPTION_KEY` (a leak of one must not weaken
the other) and must be rotatable — rotating it requires recomputing every blind
index, so version the blind-index column the same way ciphertext is versioned.

## Cross-tenant IDOR static analysis (from threat-model T1)

`threat-model.md` §T1 notes the residual risk of a new query missing its
`.where(Model.org_id == p.org_id)` clause. **Implemented (P3):**
`backend/tools/idor_lint.py` parses `app/routers` and flags any
`select(<OrgScoped model>)` whose enclosing function never references `org_id`.
Legitimately org-independent queries (scoped by the caller's own id or a signed
token) are exempted with an inline `# idor-safe: <reason>` marker. It runs both
standalone (`python -m tools.idor_lint`) and as part of the test suite
(`tests/test_idor_lint.py`), so a new unscoped query fails CI.

## Load / stress testing (from verification-checklist §"NOT in this checklist")

**Implemented (P3):** a Locust profile under `backend/tests/load/` drives the
public guest-booking surface — `GET /pub/orgs/{slug}`, `POST /pub/slots`
(availability search — the hot path), and an opt-in `POST /pub/book/guest`
write. Locust is a load-only dependency (`tests/load/requirements.txt`), kept
out of the app image and out of pytest collection. See
`backend/tests/load/README.md` for how to run it. (The endpoint is
`/pub/slots`, not the earlier-noted `/pub/availability`.)

