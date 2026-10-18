import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { ADMIN_EMAIL, STAFF_PASSWORD, loginViaUI, registerViaUI } from "./helpers";

/** WCAG 2.1 A/AA automated checks. Automated scans catch only a subset of issues; they do not replace manual review. */
async function scan(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  return results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
}

const PUBLIC = ["/", "/schemes", "/services", "/documents", "/assistant", "/complaints", "/login", "/register"];

for (const path of PUBLIC) {
  test(`no serious accessibility violations: ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("load");
    expect(await scan(page)).toEqual([]);
  });
}

test("no serious accessibility violations: Tamil interface", async ({ page }) => {
  await page.goto("/complaints");
  await page.getByRole("button", { name: "தமிழ்" }).click();
  await page.waitForLoadState("load");
  expect(await scan(page)).toEqual([]);
});

test("no serious accessibility violations: complaint form (signed in)", async ({ page }) => {
  await registerViaUI(page, "A11y Citizen");
  await page.goto("/complaints");
  await page.waitForLoadState("load");
  expect(await scan(page)).toEqual([]);
});

test("no serious accessibility violations: admin console", async ({ page }) => {
  await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "/admin");
  await expect(page.getByText("Active Schemes")).toBeVisible();
  expect(await scan(page)).toEqual([]);
});

test("pages can be operated by keyboard: skip to a control with Tab and see a visible focus ring", async ({ page }) => {
  await page.goto("/login");
  await page.keyboard.press("Tab");
  const focused = await page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el) return null;
    const cs = getComputedStyle(el);
    return { tag: el.tagName, outline: cs.outlineStyle, shadow: cs.boxShadow };
  });
  expect(focused).not.toBeNull();
  expect(focused!.outline !== "none" || focused!.shadow !== "none").toBe(true);
});
