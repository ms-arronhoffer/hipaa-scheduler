import { expect, test } from "@playwright/test";

// Golden-path booking flow against a live stack.
// Preconditions (seed script): one Org with one Office, one Provider, one
// AppointmentType with duration=30 and public bookable=true, and at least one
// availability window in the next 7 days.
//
// This test intentionally does NOT auth as staff — it exercises the fully
// public /pub/* endpoints exposed to unauthenticated patients, which is the
// most security-sensitive surface (no session, hits the DB).

test.describe("public booking (guest)", () => {
  test("patient can select a slot and submit a guest booking", async ({ page }) => {
    await page.goto("/");

    // Landing → pick office/provider/type. Selectors use accessible names
    // (Cloudscape components expose role=combobox / role=button reliably).
    await expect(page.getByRole("heading", { name: /book an appointment/i })).toBeVisible();

    await page.getByRole("combobox", { name: /appointment type/i }).click();
    await page.getByRole("option").first().click();

    await page.getByRole("button", { name: /find times/i }).click();

    // First offered slot in the returned list.
    const firstSlot = page.getByRole("button", { name: /\d{1,2}:\d{2}/ }).first();
    await expect(firstSlot).toBeVisible({ timeout: 10_000 });
    await firstSlot.click();

    // Guest identity form.
    await page.getByLabel(/first name/i).fill("Test");
    await page.getByLabel(/last name/i).fill("Patient");
    await page.getByLabel(/email/i).fill(`e2e+${Date.now()}@example.test`);
    await page.getByLabel(/phone/i).fill("5555550100");
    await page.getByLabel(/date of birth/i).fill("1990-01-01");

    await page.getByRole("button", { name: /confirm booking/i }).click();

    await expect(page.getByText(/appointment confirmed/i)).toBeVisible({
      timeout: 10_000,
    });

    // Confirmation must NOT leak internal IDs / MRN in the visible copy —
    // the plan's PHI-in-URL/UI invariant. A UUID pattern in body text = fail.
    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });
});
