import { defineConfig, devices } from "@playwright/test";

// E2E harness for the patient booking + intake flow (see plan §Testing Strategy).
// Playwright is intentionally NOT a runtime dependency of the containers —
// dev tools only. Install locally with:
//   npm i -D @playwright/test && npx playwright install
//
// Run against a running stack:
//   PLAYWRIGHT_BASE_URL=https://portal.localhost npx playwright test
//
// CI can spin up docker compose_local.yml and point at the patient-portal port.

const PORTAL_URL =
  process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:4002";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: PORTAL_URL,
    trace: "on-first-retry",
    // Deliberately DO NOT record video by default — patient portal renders PHI
    // even in seeded test orgs. Enable per-project when investigating.
    video: "off",
    screenshot: "only-on-failure",
    ignoreHTTPSErrors: true,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
  ],
});
