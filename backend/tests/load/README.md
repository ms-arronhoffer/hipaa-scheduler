# Load / stress testing — public guest booking

Locust profile for the unauthenticated booking surface, the endpoints most
exposed to traffic spikes because they need no login:

- `GET  /api/v1/pub/orgs/{slug}` — slug → org resolution
- `POST /api/v1/pub/slots` — availability search (the hot, DB-heavy path)
- `POST /api/v1/pub/book/guest` — guest booking write (optional, off by default)

Tracked in `docs/hipaa/backlog.md` and `docs/verification-checklist.md` as
capacity work that is **not** part of the correctness test suite — it is never
collected by `pytest` (it lives outside the imported test paths and has no
`test_` functions).

## Install

Locust is intentionally *not* in the app image / `requirements.txt`; it is a
load-tool only:

```bash
pip install -r backend/tests/load/requirements.txt
```

## Run

Point it at a running instance and provide a real org slug plus the office /
provider / appointment-type UUIDs to exercise (reads only by default):

```bash
export TARGET_HOST=https://staging.example.com
export ORG_SLUG=acme-clinic
export OFFICE_ID=...            # UUID
export PROVIDER_ID=...          # UUID
export APPOINTMENT_TYPE_ID=...  # UUID
# export ENABLE_GUEST_BOOKING=1  # opt in to POST /book/guest writes

locust -f backend/tests/load/locustfile.py --host "$TARGET_HOST"
```

Then open http://localhost:8089 to set the user count / spawn rate, or run
headless:

```bash
locust -f backend/tests/load/locustfile.py --host "$TARGET_HOST" \
  --headless -u 200 -r 20 -t 5m
```

> Only run against staging / load environments. Guest booking writes real
> appointments + `PatientAccount` rows, so keep `ENABLE_GUEST_BOOKING` unset
> unless the target is disposable.
