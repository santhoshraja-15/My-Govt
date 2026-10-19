import { expect, test, type Page } from "@playwright/test";
import { API } from "./helpers";

test.use({ reducedMotion: "reduce" });

const MAGALIR = "Kalaignar Magalir Urimai Thogai";   // E2E database: two labelled DEMO rules (woman, income <= 250000)

async function openScheme(page: Page, search: string) {
  await page.goto("/schemes");
  await page.getByLabel("Search schemes").fill(search);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.getByTestId("scheme-card")).toHaveCount(1);
  await page.getByTestId("scheme-card").click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(new RegExp(search.split(" ")[0], "i"));
}

async function openChecker(page: Page) {
  await page.getByTestId("check-my-eligibility").click();
  await expect(page.getByTestId("eligibility-checker")).toBeVisible();
}

async function answer(page: Page, values: Record<string, string>) {
  for (const [k, v] of Object.entries(values)) {
    const f = page.getByTestId(`field-${k}`);
    if ((await f.evaluate((e) => e.tagName)) === "SELECT") await f.selectOption(v); else await f.fill(v);
  }
}

test.describe("eligibility checker (was unreachable from the UI)", () => {
  test("a woman under the income limit is shown as meeting the recorded criteria, with per-criterion results", async ({ page }) => {
    await openScheme(page, MAGALIR);
    await openChecker(page);
    await expect(page.getByTestId("checker-demo-note")).toContainText("demonstration rules");
    await answer(page, { gender: "female", annual_income: "180000" });
    await page.getByTestId("check-eligibility").click();
    const res = page.getByTestId("eligibility-result");
    await expect(res).toHaveAttribute("data-overall", "ELIGIBLE");
    await expect(page.getByTestId("eligibility-headline")).toContainText("appear to meet the recorded criteria");
    await expect(page.getByTestId("eligibility-checker")).toContainText("not an application and not an approval");
    await expect(page.getByTestId("rule-results").locator("tbody tr")).toHaveCount(2);
    await expect(page.getByTestId("rule-results").locator('tr[data-outcome="PASS"]')).toHaveCount(2);
    // the rule list on the same tab reflects the same outcomes
    await expect(page.getByText("You meet this criterion").first()).toBeAttached();
    await page.getByTestId("recheck").click();
    await expect(page.getByTestId("eligibility-form")).toBeVisible();
  });

  test("ineligible, boundary and incomplete cases", async ({ page }) => {
    await openScheme(page, MAGALIR);
    await openChecker(page);
    const outcome = async (values: Record<string, string>) => {
      await answer(page, values);
      await page.getByTestId("check-eligibility").click();
      const overall = await page.getByTestId("eligibility-result").getAttribute("data-overall");
      await page.getByTestId("recheck").click();
      return overall;
    };
    expect(await outcome({ gender: "male", annual_income: "180000" })).toBe("NOT_ELIGIBLE");
    expect(await outcome({ gender: "female", annual_income: "250000" })).toBe("ELIGIBLE");          // boundary: <= 250000
    expect(await outcome({ gender: "female", annual_income: "250001" })).toBe("NOT_ELIGIBLE");
    await page.getByTestId("clear-answers").click();
    await answer(page, { age: "40" });                                                              // nothing the rules ask for
    await page.getByTestId("check-eligibility").click();
    await expect(page.getByTestId("eligibility-result")).toHaveAttribute("data-overall", "INSUFFICIENT_DATA");
    await expect(page.getByTestId("missing-info")).toContainText("gender");
    await expect(page.getByTestId("eligibility-headline")).toContainText("Not enough information");
  });

  test("invalid answers are explained next to the field and nothing is sent", async ({ page }) => {
    await openScheme(page, MAGALIR);
    await openChecker(page);
    let sent = 0;
    page.on("request", (r) => { if (r.url().includes("/eligibility")) sent++; });
    await answer(page, { age: "-5", annual_income: "-1" });
    await page.getByTestId("check-eligibility").click();
    await expect(page.getByTestId("error-age")).toContainText("between 0 and 120");
    await expect(page.getByTestId("error-annual_income")).toBeVisible();
    await page.getByTestId("field-age").fill("200");
    await page.getByTestId("check-eligibility").click();
    await expect(page.getByTestId("error-age")).toBeVisible();
    await page.getByTestId("field-age").fill("30.5");
    await page.getByTestId("check-eligibility").click();
    await expect(page.getByTestId("error-age")).toContainText("whole years");
    await page.getByTestId("field-age").fill("30");
    await page.getByTestId("field-annual_income").fill("0");
    await page.getByTestId("field-occupation").fill("x".repeat(90));
    await page.getByTestId("check-eligibility").click();
    await expect(page.getByTestId("error-occupation")).toContainText("At most 80");
    expect(sent).toBe(0);
    await expect(page.getByLabel("Age (years)")).toHaveAttribute("aria-invalid", "false");     // labels are really associated
  });

  test("a scheme without recorded rules says so instead of pretending to evaluate", async ({ page }) => {
    await openScheme(page, "breakfast");
    await page.getByTestId("check-my-eligibility").click();
    await expect(page.getByTestId("eligibility-no-rules")).toContainText("cannot evaluate");
    await expect(page.getByTestId("check-eligibility")).toHaveCount(0);
  });

  test("the API rejects out-of-range facts too", async ({ request }) => {
    const id = (await (await request.get(`${API}/schemes?page_size=1`)).json()).items[0].scheme_id;
    for (const bad of [{ age: -5 }, { annual_income: -1 }, { family_size: 0 }]) {
      expect((await request.post(`${API}/schemes/${id}/eligibility`, { data: bad })).status()).toBe(422);
    }
  });
});

test.describe("service details (links used to 404)", () => {
  test("every service card opens a real detail page with honest fee information", async ({ page, request }) => {
    const list = await (await request.get(`${API}/services?page_size=50`)).json();
    await page.goto("/services");
    await expect(page.getByTestId("service-card")).toHaveCount(Math.min(12, list.total));
    await page.getByTestId("service-card").first().click();
    await expect(page).toHaveURL(/\/services\/[0-9a-f-]{36}/);
    await expect(page.getByTestId("service-name")).not.toBeEmpty();
    await expect(page.getByTestId("fees-section")).toBeVisible();
    await expect(page.getByTestId("charges-unconfirmed-detail")).toContainText("not been confirmed");   // seeded records are provisional
    await expect(page.getByTestId("fees-section")).not.toContainText("₹");
    await expect(page.getByTestId("source-info")).toContainText("Not yet verified");
    await expect(page.getByTestId("requirements-section")).toBeVisible();
    const apply = page.getByTestId("apply-link");
    if (await apply.count()) {
      await expect(apply).toHaveAttribute("target", "_blank");
      await expect(apply).toHaveAttribute("rel", /noopener/);
    }
    await page.goBack();
    await expect(page.getByTestId("service-card").first()).toBeVisible();
  });

  test("every listed service id resolves; unknown or malformed ids show a clear not-found state", async ({ page, request }) => {
    const list = await (await request.get(`${API}/services?page_size=50`)).json();
    for (const s of list.items) {
      await page.goto(`/services/${s.service_id}`);
      await expect(page.getByTestId("service-detail")).toBeVisible();
    }
    for (const bad of ["00000000-0000-0000-0000-000000000000", "not-a-uuid"]) {
      await page.goto(`/services/${bad}`);
      await expect(page.getByTestId("service-not-found")).toBeVisible();
    }
  });
});

test.describe("filters match the data", () => {
  test("service category pills come from the API and each one returns results", async ({ page, request }) => {
    const cats: string[] = await (await request.get(`${API}/services/categories/list`)).json();
    await page.goto("/services");
    for (const c of cats) {
      await page.getByTestId(`service-category-${c}`).click();
      await expect(page.getByTestId("empty-state")).toHaveCount(0);
      await expect(page.getByTestId("service-card").first()).toBeVisible();
    }
    await page.getByTestId("service-category-All").click();
    await expect(page.getByTestId("service-card").first()).toBeVisible();
  });

  test("scheme category and level filters come from the API and each category returns results", async ({ page, request }) => {
    const cats: string[] = await (await request.get(`${API}/schemes/categories/list`)).json();
    await page.goto("/schemes");
    await page.getByRole("button", { name: "Toggle filters" }).click();
    const select = page.getByLabel("Category");
    const options = await select.locator("option").evaluateAll((o) => o.map((x) => (x as HTMLOptionElement).value));
    expect(options).toEqual(["All", ...cats]);
    for (const c of cats) {
      await select.selectOption(c);
      await expect(page.getByTestId("empty-state")).toHaveCount(0);
      await expect(page.getByTestId("scheme-card").first()).toBeVisible();
    }
    await select.selectOption("All");
    await page.getByLabel("Level").selectOption("central");
    await expect(page.getByTestId("scheme-card")).toHaveCount(1);        // PM-Kisan is the only central scheme
    const centralCategory = (await (await request.get(`${API}/schemes?level=central`)).json()).items[0].category;
    await select.selectOption(cats.find((c) => c !== centralCategory)!);
    await expect(page.getByTestId("empty-state")).toBeVisible();          // filters combine (AND): central AND another category = nothing
  });
});

test.describe("labels, layout and error pages", () => {
  test("search boxes have accessible names", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Search schemes, services, or ask a question")).toBeVisible();
    await page.goto("/schemes");
    await expect(page.getByRole("search").getByLabel("Search schemes")).toBeVisible();
    await page.goto("/services");
    await expect(page.getByRole("search").getByLabel("Search services")).toBeVisible();
    await page.goto("/documents");
    await expect(page.getByRole("search").getByLabel("Search documents")).toBeVisible();
  });

  for (const path of ["/schemes", "/services", "/documents", "/schemes?tab=eligibility"]) {
    test(`no horizontal scrolling on a phone: ${path}`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    });
  }

  test("unknown pages show a styled 404 with a way back", async ({ page }) => {
    const resp = await page.goto("/definitely-not-a-page");
    expect(resp?.status()).toBe(404);
    await expect(page.getByTestId("not-found")).toContainText("Page not found");
    await page.getByRole("link", { name: "Go to the home page" }).click();
    await expect(page).toHaveURL(/localhost:\d+\/$/);
  });

  test("the architecture page makes no protected API calls before sign-in", async ({ page }) => {
    const protectedCalls: string[] = [];
    page.on("request", (r) => { if (r.url().includes("/api/v1/architecture")) protectedCalls.push(r.url()); });
    await page.goto("/database-architecture");
    await expect(page).toHaveURL(/\/login/);
    expect(protectedCalls).toEqual([]);
  });
});
