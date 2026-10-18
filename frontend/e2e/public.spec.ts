import { expect, test } from "@playwright/test";
import { API } from "./helpers";

test.describe("landing page", () => {
  test("shows live counts from the API and no invented figures", async ({ page, request }) => {
    const stats = await (await request.get(`${API}/public/stats`)).json();
    await page.goto("/");
    await expect(page.getByTestId("stat-schemes")).toContainText(String(stats.schemes));
    await expect(page.getByTestId("stat-districts")).toContainText(String(stats.districts));
    await expect(page.getByTestId("stat-services")).toContainText(String(stats.services));
    const body = await page.locator("body").innerText();
    expect(body).not.toContain("75M"); // previously a fabricated "Citizens Served" figure
    expect(body).not.toContain("30+");
    expect(body).not.toContain("20+");
  });

  test("primary navigation reaches every section", async ({ page }) => {
    for (const [name, url] of [
      ["Schemes", /\/schemes/], ["Services", /\/services/], ["Complaints", /\/complaints/], ["AI Assistant", /\/assistant/],
    ] as const) {
      await page.goto("/");
      await page.getByRole("link", { name, exact: true }).first().click();
      await expect(page).toHaveURL(url);
    }
  });

  test("sign in link resolves to a real page", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("link", { name: "Sign In" }).first().click();
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();
  });
});

test.describe("language", () => {
  test("toggle switches interface text to Tamil and back, and persists", async ({ page }) => {
    await page.goto("/schemes");
    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link", { name: "Schemes" })).toBeVisible();
    await page.getByRole("button", { name: "தமிழ்" }).click();
    await expect(nav.getByRole("link", { name: "திட்டங்கள்" })).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", "ta");
    await page.reload();
    await expect(nav.getByRole("link", { name: "திட்டங்கள்" })).toBeVisible(); // persisted
    await page.getByRole("button", { name: "EN" }).click();
    await expect(nav.getByRole("link", { name: "Schemes" })).toBeVisible();
  });

  test("Tamil names from the database render", async ({ page }) => {
    await page.goto("/schemes");
    await expect(page.getByTestId("scheme-card").first()).toBeVisible();
    await expect(page.getByText("முதலமைச்சரின் காலை உணவுத் திட்டம்")).toBeVisible();
  });
});
