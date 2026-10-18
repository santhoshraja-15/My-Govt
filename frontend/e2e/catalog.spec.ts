import { expect, test } from "@playwright/test";
import { alertBox } from "./helpers";

test.describe("scheme discovery", () => {
  test("lists schemes, each labelled with its verification status", async ({ page }) => {
    await page.goto("/schemes");
    await expect(page.getByTestId("scheme-card").first()).toBeVisible();
    await expect(page.getByText(/12 schemes found/)).toBeVisible();
    const badges = page.getByTestId("scheme-card").getByTestId("verification-badge");
    expect(await badges.count()).toBeGreaterThan(0);
    // Nothing is presented as "Verified": no official document evidence is recorded.
    for (const s of await badges.evaluateAll((els) => els.map((e) => e.getAttribute("data-status")))) {
      expect(s).not.toBe("official_verified");
    }
    await expect(page.getByText("Provisional").first()).toBeVisible();
  });

  test("search filters results and shows an empty state for no match", async ({ page }) => {
    await page.goto("/schemes");
    await page.getByPlaceholder("Search schemes…").fill("breakfast");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText(/1 scheme found/)).toBeVisible();
    await expect(page.getByTestId("scheme-card")).toHaveCount(1);
    await page.getByPlaceholder("Search schemes…").fill("zzqqxx");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByTestId("empty-state")).toBeVisible();
  });

  test("detail page shows source status", async ({ page }) => {
    await page.goto("/schemes");
    await page.getByPlaceholder("Search schemes…").fill("breakfast");
    await page.getByRole("button", { name: "Search" }).click();
    await page.getByTestId("scheme-card").first().click();
    await expect(page.getByRole("heading", { name: /Breakfast/ })).toBeVisible();
    await expect(page.getByTestId("verification-badge").first()).toHaveAttribute("data-status", "provisional");
  });

  test("shows an error with retry when the API fails (not a misleading empty list)", async ({ page }) => {
    await page.route("**/api/v1/schemes?*", (r) =>
      r.fulfill({ status: 500, contentType: "application/json", body: '{"code":"INTERNAL_ERROR","message":"boom"}' }));
    await page.goto("/schemes");
    await expect(alertBox(page)).toBeVisible();
    await expect(page.getByTestId("empty-state")).toHaveCount(0);
    await page.unroute("**/api/v1/schemes?*");
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(page.getByTestId("scheme-card").first()).toBeVisible();
  });
});

test.describe("citizen services", () => {
  test("lists all services with verification labels and search works", async ({ page }) => {
    await page.goto("/services");
    await expect(page.getByTestId("service-card").first()).toBeVisible();
    await expect(page.getByText(/10 services/)).toBeVisible();
    const statuses = await page.getByTestId("service-card").getByTestId("verification-badge")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-status")));
    expect(statuses.length).toBeGreaterThan(0);
    for (const s of statuses) expect(s).toBe("provisional");
    await page.getByPlaceholder("Search services…").fill("Ration Card");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByTestId("service-card")).toHaveCount(1);
  });

  test("shows an error state when the API is unreachable", async ({ page }) => {
    await page.route("**/api/v1/services?*", (r) => r.abort());
    await page.goto("/services");
    await expect(alertBox(page)).toContainText(/reach the server|Could not load/i);
  });
});
