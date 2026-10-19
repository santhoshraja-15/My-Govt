import AxeBuilder from "@axe-core/playwright";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { ADMIN_EMAIL, API, OFFICER_EMAIL, STAFF_PASSWORD, SYSADMIN_EMAIL, apiCitizen, bearer, loginViaUI, registerViaUI } from "./helpers";

test.use({ reducedMotion: "reduce" });

async function adminToken(request: APIRequestContext, email = ADMIN_EMAIL) {
  const r = await request.post(`${API}/auth/login`, { data: { email, password: STAFF_PASSWORD } });
  return (await r.json()).access_token as string;
}
const get = async (request: APIRequestContext, token: string, path: string) =>
  (await request.get(`${API}/architecture${path}`, { headers: bearer(token) })).json();

async function openAsAdmin(page: Page, email = ADMIN_EMAIL, tab = "") {
  await loginViaUI(page, email, STAFF_PASSWORD, `/database-architecture${tab ? `?tab=${tab}` : ""}`);
  await expect(page.getByTestId("database-architecture")).toBeVisible();
}

test.describe("navigation and access", () => {
  test("administrators see the Database Architecture button; it opens the page and is marked active", async ({ page }) => {
    await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "");
    await expect(page).toHaveURL(/\/admin/);
    const nav = page.getByTestId("nav-database-architecture");
    await expect(nav).toBeVisible();
    await expect(nav).toHaveText(/Database Architecture/);
    await nav.click();
    await expect(page).toHaveURL(/\/database-architecture/);
    await expect(page.getByRole("heading", { name: "Database Architecture Explorer" })).toBeVisible();
    await expect(page.getByTestId("nav-database-architecture")).toHaveAttribute("aria-current", "page");
  });

  test("the admin console sidebar links to it as well", async ({ page }) => {
    await loginViaUI(page, SYSADMIN_EMAIL, STAFF_PASSWORD, "");
    await page.getByTestId("admin-database-architecture").click();
    await expect(page).toHaveURL(/\/database-architecture/);
  });

  test("direct URL works for both administrator roles and survives a reload", async ({ page }) => {
    for (const email of [ADMIN_EMAIL, SYSADMIN_EMAIL]) {
      await openAsAdmin(page, email, "er");
      await page.reload();
      await expect(page.getByTestId("panel-er")).toBeVisible();
      await page.getByRole("button", { name: "Sign out" }).click();
    }
  });

  test("citizens, officers and anonymous visitors cannot use it and never see the button", async ({ page, request }) => {
    await page.goto("/database-architecture");
    await expect(page).toHaveURL(/\/login\?next=/);
    await registerViaUI(page, "Curious Citizen");
    await expect(page.getByTestId("nav-database-architecture")).toHaveCount(0);
    await page.goto("/database-architecture");
    await expect(page).toHaveURL(/\/dashboard/);
    await page.getByRole("button", { name: "Sign out" }).click();
    await loginViaUI(page, OFFICER_EMAIL, STAFF_PASSWORD, "");
    await expect(page).toHaveURL(/\/officer/);
    await expect(page.getByTestId("officer-console")).toBeVisible();
    await expect(page.getByTestId("nav-database-architecture")).toHaveCount(0);
    await page.goto("/database-architecture");
    await expect(page).toHaveURL(/\/officer/);
    // the API refuses regardless of the UI
    const citizen = await apiCitizen(request);
    for (const t of [citizen.token, await adminToken(request, OFFICER_EMAIL)]) {
      expect((await request.get(`${API}/architecture/overview`, { headers: bearer(t) })).status()).toBe(403);
    }
    expect((await request.get(`${API}/architecture/tables`)).status()).toBe(401);
  });
});

test.describe("real metadata", () => {
  test("headline numbers equal what the API reads from the database catalog", async ({ page, request }) => {
    const token = await adminToken(request);
    const o = await get(request, token, "/overview");
    await openAsAdmin(page);
    await expect(page.getByTestId("kpi-tables")).toContainText(String(o.counts.tables));
    await expect(page.getByTestId("kpi-fks")).toContainText(String(o.counts.foreign_keys));
    await expect(page.getByTestId("kpi-schemas")).toContainText(String(o.counts.schemas));
    await expect(page.getByTestId("kpi-columns")).toContainText(String(o.counts.columns));
    expect(o.counts.tables).toBeGreaterThan(40);
    await expect(page.getByTestId("technology-list")).toContainText("PostgreSQL");
  });

  test("architecture diagram: real components, honest availability, selectable details", async ({ page }) => {
    await openAsAdmin(page);
    await expect(page.getByTestId("arch-node")).toHaveCount(9);
    const ids = await page.getByTestId("arch-node").evaluateAll((els) => els.map((e) => e.getAttribute("data-component")));
    expect(ids.sort()).toEqual(["api", "frontend", "minio", "neo4j", "pgvector", "postgis", "postgresql", "redis", "services"]);
    await expect(page.locator('[data-testid="arch-node"][data-component="postgresql"]')).toHaveAttribute("data-status", "active");
    // services that are not running in the test stack are reported, not hidden, and nothing crashes
    await expect(page.locator('[data-testid="arch-node"][data-component="redis"]')).not.toHaveAttribute("data-status", "active");
    await expect(page.locator('[data-testid="arch-node"][data-component="neo4j"]')).toHaveAttribute("data-status", "disabled");
    await page.locator('[data-testid="arch-node"][data-component="minio"]').dispatchEvent("click");
    const detail = page.getByTestId("arch-detail");
    await expect(detail).toHaveAttribute("data-component", "minio");
    await expect(detail).toContainText("not implemented");
    await page.locator('[data-testid="arch-node"][data-component="postgis"]').dispatchEvent("click");
    await expect(detail).toContainText("administration.district");
    await expect(page.getByTestId("architecture-legend")).toContainText("optional");
    const text = await page.locator("body").innerText();
    expect(text).not.toMatch(/postgresql:\/\/|password|secret/i);
  });

  test("ER diagram: one node per table, highlighting matches the real foreign keys", async ({ page, request }) => {
    const token = await adminToken(request);
    const rels = await get(request, token, "/relationships");
    const tables = await get(request, token, "/tables");
    await openAsAdmin(page, ADMIN_EMAIL, "er");
    await expect(page.getByTestId("er-node")).toHaveCount(tables.total);
    const key = "complaints.complaint";
    const connected = new Set<string>([key]);
    for (const f of rels.foreign_keys) if (f.from_table === key || f.to_table === key) { connected.add(f.from_table); connected.add(f.to_table); }
    await page.locator(`[data-testid="er-node"][data-table="${key}"]`).dispatchEvent("click");
    await expect(page.getByTestId("table-detail")).toHaveAttribute("data-table", key);
    await expect(page.locator('[data-testid="er-node"][data-dim="false"]')).toHaveCount(connected.size);
    await expect(page.locator(`[data-testid="er-node"][data-table="${key}"]`)).toHaveAttribute("data-selected", "true");
    await expect(page.getByTestId("er-counts")).toContainText(`${connected.size - 1} connected`);
    // the detail panel lists the same relationships
    const detail = await get(request, token, "/tables/complaints/complaint");
    await expect(page.getByTestId("references-list").locator("li")).toHaveCount(detail.references.length);
    await expect(page.getByTestId("column-row")).toHaveCount(detail.columns.length);
    // clicking a related table in the panel moves the selection
    await page.getByTestId("references-list").getByTestId("related-table").first().click();
    await expect(page.getByTestId("table-detail")).not.toHaveAttribute("data-table", key);
  });

  test("ER diagram: focus mode shows exactly the selected table and its related tables", async ({ page, request }) => {
    const token = await adminToken(request);
    const rels = await get(request, token, "/relationships");
    const key = "complaints.complaint_category";
    const connected = new Set<string>([key]);
    for (const f of rels.foreign_keys) if (f.from_table === key || f.to_table === key) { connected.add(f.from_table); connected.add(f.to_table); }
    await openAsAdmin(page, ADMIN_EMAIL, "er");
    await page.getByTestId("er-focus").check();
    await expect(page.getByTestId("er-counts")).toContainText("Select a table to focus on it");
    await page.locator(`[data-testid="er-node"][data-table="${key}"]`).dispatchEvent("click");
    await expect(page.getByTestId("er-node")).toHaveCount(connected.size);
    for (const t of connected) await expect(page.locator(`[data-testid="er-node"][data-table="${t}"]`)).toHaveCount(1);
    await page.getByTestId("er-focus").uncheck();
    await expect(page.getByTestId("er-node").first()).toBeVisible();
    expect(await page.getByTestId("er-node").count()).toBeGreaterThan(connected.size);
  });

  test("ER diagram: search, schema filter, compact mode, fit and reset", async ({ page, request }) => {
    const token = await adminToken(request);
    const total = (await get(request, token, "/tables")).total;
    await openAsAdmin(page, ADMIN_EMAIL, "er");
    await page.getByTestId("er-search").fill("complaint_history");
    await expect(page.getByTestId("er-node").first()).toBeVisible();
    const filtered = await page.getByTestId("er-node").count();
    expect(filtered).toBeGreaterThan(0);
    expect(filtered).toBeLessThan(total);
    await expect(page.locator('[data-testid="er-node"][data-table="complaints.complaint_history"]')).toHaveCount(1);
    await page.getByTestId("er-search").fill("zzz-no-such-table");
    await expect(page.getByTestId("er-empty")).toBeVisible();
    await page.getByTestId("er-reset").click();
    await expect(page.getByTestId("er-node")).toHaveCount(total);
    await page.getByTestId("schema-chip-audit").click();
    await expect(page.locator('[data-testid="er-node"][data-table="audit.audit_log"]')).toHaveCount(0);
    await expect(page.getByTestId("er-node")).toHaveCount(total - 1);
    await page.getByTestId("schema-chip-audit").click();
    await expect(page.getByTestId("er-node")).toHaveCount(total);
    await page.getByTestId("er-compact").check();
    await expect(page.getByTestId("er-node").first().locator("li")).toHaveCount(0);
    await page.getByTestId("er-compact").uncheck();
    await page.getByTestId("er-fit").click();
    await page.getByTestId("er-inferred").check();
    await expect(page.getByTestId("er-counts")).toContainText("relationship");
    await expect(page.getByTestId("er-legend")).toContainText("not enforced");
  });

  test("relational schema and normalization are derived from the catalog", async ({ page, request }) => {
    const token = await adminToken(request);
    const sch = await get(request, token, "/schema");
    await openAsAdmin(page, ADMIN_EMAIL, "schema");
    await expect(page.getByTestId("relation-list").locator("li")).toHaveCount(sch.total);
    await page.getByTestId("relational-search").fill("complaint_history");
    await expect(page.getByTestId("relation-list").locator('li[data-relation="complaints.complaint_history"]')).toContainText("COMPLAINT_HISTORY(PK:history_id");
    await expect(page.getByTestId("relational-count")).toContainText(`of ${sch.total}`);
    await expect(page.getByTestId("normalization")).toContainText("Third normal form is deliberately not claimed");
  });

  test("implementation: table details, hidden sensitive data, runnable read-only examples", async ({ page, request }) => {
    const token = await adminToken(request);
    await openAsAdmin(page, ADMIN_EMAIL, "implementation");
    await page.getByTestId("impl-search").fill("app_user");
    await page.locator('[data-testid="impl-table-list"] button[data-table="identity.app_user"]').click();
    await expect(page.getByTestId("detail-title")).toHaveText("identity.app_user");
    await expect(page.getByTestId("sample-unavailable")).toContainText("personal or operational data");
    await expect(page.getByTestId("table-detail")).not.toContainText("@example.com");
    const detail = await get(request, token, "/tables/identity/app_user");
    await expect(page.getByTestId("column-row")).toHaveCount(detail.columns.length);
    await page.getByTestId("impl-search").fill("");
    await page.locator('[data-testid="impl-table-list"] button[data-table="administration.department"]').click();
    await expect(page.getByTestId("sample-table")).toContainText("department_name");
    await expect(page.getByTestId("sample-table")).not.toContainText("contact_email");
    await expect(page.getByTestId("table-detail")).toContainText("Hidden:");
    await expect(page.getByTestId("database-files")).toContainText("001_schema.sql");
    const card = page.locator('[data-testid="example-card"][data-example="schemes_by_department"]');
    await card.getByTestId("run-example").click();
    await expect(card.getByTestId("example-result")).toContainText("scheme_name");
    expect(await card.getByTestId("example-result").locator("tbody tr").count()).toBeGreaterThan(0);
    await card.getByTestId("explain-example").click();
    await expect(card.getByTestId("example-plan")).toContainText(/Scan|Join/);
  });

  test("advanced concepts: implemented items are real and absent ones are labelled", async ({ page, request }) => {
    const token = await adminToken(request);
    const adv = await get(request, token, "/advanced");
    await openAsAdmin(page, ADMIN_EMAIL, "advanced");
    await expect(page.getByTestId("concept-card")).toHaveCount(adv.concepts.length);
    await expect(page.locator('[data-concept="Triggers"]')).toHaveAttribute("data-status", "Implemented");
    await expect(page.locator('[data-concept="Redis"]')).toHaveAttribute("data-status", "Not implemented");
    await expect(page.locator('[data-concept="Stored procedures (CALL)"]')).toHaveAttribute("data-status", "Not implemented");
    await page.locator('[data-concept="Views"] summary').click();
    await expect(page.locator('[data-concept="Views"]')).toContainText("v_sla_breached");
  });

  test("API failure shows an error with retry instead of an empty page", async ({ page }) => {
    await openAsAdmin(page);
    await page.route("**/api/v1/architecture/tables", (r) => r.abort());
    await page.reload();
    await expect(page.getByRole("alert").first()).toContainText(/Cannot reach the server|failed/i);
    await page.unroute("**/api/v1/architecture/tables");
    await page.getByRole("button", { name: "Try again" }).first().click();
    await expect(page.getByTestId("kpi-tables")).toBeVisible();
  });
});

test.describe("responsive and accessible", () => {
  test("phone width: no horizontal scrolling on any tab", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openAsAdmin(page);
    for (const tab of ["architecture", "er", "schema", "implementation", "advanced"]) {
      await page.getByTestId(`tab-${tab}`).click();
      await expect(page.getByTestId(`panel-${tab}`)).toBeVisible();
      await page.waitForTimeout(400);
      const info = await page.evaluate(() => {
        const w = document.documentElement.clientWidth;
        const offenders = [...document.querySelectorAll("body *")].map((e) => ({ e, r: e.getBoundingClientRect() })).filter(({ r }) => r.width > 0 && r.right > w + 0.5)
          .slice(0, 6).map(({ e, r }) => `${e.tagName}.${String(e.className).slice(0, 50)} right=${r.right.toFixed(0)}`);
        return { overflow: document.documentElement.scrollWidth - w, viewport: w, offenders };
      });
      expect(info.overflow, `${tab}: ${JSON.stringify(info)}`).toBeLessThanOrEqual(1);
    }
    await page.getByTestId("tab-er").click();
    const box = await page.getByTestId("er-diagram").locator(".react-flow").boundingBox();
    expect(box && box.width > 300 && box.height > 400).toBeTruthy();
  });

  test("tablet width keeps the tabs and diagram usable", async ({ page }) => {
    await page.setViewportSize({ width: 820, height: 1100 });
    await openAsAdmin(page, ADMIN_EMAIL, "er");
    await expect(page.getByTestId("er-node").first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  });

  for (const tab of ["architecture", "er", "schema", "implementation", "advanced"]) {
    test(`no serious accessibility violations: ${tab} tab`, async ({ page }) => {
      await openAsAdmin(page, ADMIN_EMAIL, tab);
      await page.waitForTimeout(800);
      const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
        .map((v) => `${v.id} (${v.impact}): ${v.nodes.length} node(s), e.g. ${v.nodes[0]?.target.join(" ")}`);
      expect(bad).toEqual([]);
    });
  }

  test("tabs are keyboard operable", async ({ page }) => {
    await openAsAdmin(page);
    await page.getByTestId("tab-er").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("panel-er")).toBeVisible();
    await expect(page.getByTestId("tab-er")).toHaveAttribute("aria-selected", "true");
  });
});
