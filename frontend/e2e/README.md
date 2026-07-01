# Playwright E2E Tests

Golden-path browser tests for the patient booking + intake flow. Kept separate
from Vitest so unit tests can run in CI without spinning up the full stack.

## Setup (one-time)

```bash
cd frontend
npm i -D @playwright/test
npx playwright install --with-deps chromium firefox
```

## Run against local stack

```bash
# From repo root
docker compose -f docker-compose_local.yml up -d
cd backend && python -m app.seed.seed_e2e   # creates a bookable org/provider/type
cd ../frontend
PLAYWRIGHT_BASE_URL=http://localhost:4002 npx playwright test
```

## Coverage

- `booking.spec.ts` — guest booking golden path; asserts no UUIDs leak into the
  visible confirmation UI (PHI-in-UI invariant).

New specs go in this directory; anything covering the staff calendar or admin
portal should point `PLAYWRIGHT_BASE_URL` at the staff (`:4000`) or admin
(`:4001`) origin respectively.
