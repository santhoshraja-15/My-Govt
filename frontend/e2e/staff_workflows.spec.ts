import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { ADMIN_EMAIL, API, CITIZEN_PASSWORD, OFFICER_EMAIL, STAFF_PASSWORD, apiCitizen, bearer, loginViaUI, registerViaUI } from "./helpers";

const OFFICER2_EMAIL = "e2e-officer2@example.com";

/** First category by name: the fixture officer (e2e_env) belongs to that category's department. */
async function firstCategoryId(request: APIRequestContext): Promise<number> {
  const cats = await (await request.get(`${API}/complaints/categories/list`)).json();
  return cats[0].category_id;
}

async function fileComplaint(request: APIRequestContext, token: string, title: string) {
  const r = await request.post(`${API}/complaints`, {
    headers: bearer(token),
    data: { title, description: "Created by an automated browser test to exercise the officer workflow.", category_id: await firstCategoryId(request) },
  });
  expect(r.status()).toBe(201);
  return (await r.json()) as { complaint_id: string; reference_number: string; status: string };
}

async function staffToken(request: APIRequestContext, email: string) {
  const r = await request.post(`${API}/auth/login`, { data: { email, password: STAFF_PASSWORD } });
  expect(r.status()).toBe(200);
  return (await r.json()).access_token as string;
}

async function noHorizontalScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test.describe("role-based landing pages and guards", () => {
  test("registering lands a citizen on their dashboard", async ({ page }) => {
    await registerViaUI(page, "Dana Dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("dashboard-greeting")).toContainText("Dana");
    await expect(page.getByTestId("stat-total")).toContainText("0");
    await expect(page.getByTestId("empty-state").first()).toContainText("not filed any complaints");
  });

  test("staff land on their own consoles after sign-in", async ({ page }) => {
    await loginViaUI(page, OFFICER_EMAIL, STAFF_PASSWORD, "");
    await expect(page).toHaveURL(/\/officer/);
    await page.getByRole("button", { name: "Sign out" }).click();
    await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "");
    await expect(page).toHaveURL(/\/admin/);
  });

  test("citizens cannot use the officer console; anonymous visitors are sent to sign in", async ({ page }) => {
    await page.goto("/officer");
    await expect(page).toHaveURL(/\/login\?next=%2Fofficer/);
    await registerViaUI(page, "Not An Officer");
    await page.goto("/officer");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByTestId("officer-console")).toHaveCount(0);
  });
});

test.describe("complaint lifecycle across citizen and officer", () => {
  test("officer assigns, progresses and resolves; the citizen sees status and remarks", async ({ page, request }) => {
    const citizen = await apiCitizen(request);
    const c = await fileComplaint(request, citizen.token, "Broken pump near the village school");

    await loginViaUI(page, OFFICER_EMAIL, STAFF_PASSWORD, "");
    await expect(page).toHaveURL(/\/officer/);
    await expect(page.getByTestId("officer-scope")).not.toHaveText(/Loading|All departments/);

    const row = page.getByTestId("staff-row").filter({ hasText: c.reference_number });
    await expect(row).toBeVisible();
    await row.getByRole("button", { name: c.reference_number }).click();
    const detail = page.getByTestId("complaint-detail");
    await expect(detail).toContainText("Broken pump near the village school");
    await expect(detail.getByTestId("detail-officer")).toHaveText("Not assigned");

    await detail.getByTestId("assign-me-btn").click();
    await expect(page.getByTestId("toast").filter({ hasText: "Assigned to you" })).toBeVisible();
    await expect(detail.getByTestId("detail-officer")).toHaveText("E2E Officer");
    await expect(detail.getByTestId("status-badge").first()).toHaveAttribute("data-status", "assigned");

    await detail.getByLabel(/Remarks/).fill("Technician visit scheduled for tomorrow");
    await detail.getByTestId("move-in_progress").click();
    await expect(page.getByTestId("toast").filter({ hasText: "In progress" })).toBeVisible();
    await expect(detail.getByTestId("timeline")).toContainText("Technician visit scheduled for tomorrow");

    // only legal next steps are offered from here (no "closed", no "assigned")
    await expect(detail.getByTestId("move-resolved")).toBeVisible();
    await expect(detail.getByTestId("move-closed")).toHaveCount(0);

    await detail.getByLabel(/Remarks/).fill("Pump repaired and tested");
    await detail.getByTestId("move-resolved").click();
    await expect(detail.getByTestId("status-badge").first()).toHaveAttribute("data-status", "resolved");

    // the citizen sees the result: API (persisted) and dashboard UI
    const mine = await (await request.get(`${API}/complaints/${c.complaint_id}`, { headers: bearer(citizen.token) })).json();
    expect(mine.status).toBe("resolved");
    expect(mine.officer_name).toBe("E2E Officer");
    expect(mine.timeline.map((h: any) => h.remarks)).toEqual(expect.arrayContaining(["Technician visit scheduled for tomorrow", "Pump repaired and tested"]));

    await page.getByRole("button", { name: "Sign out" }).click();
    await loginViaUI(page, citizen.email, CITIZEN_PASSWORD, "/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
    const recent = page.getByTestId("recent-complaints");
    await expect(recent).toContainText("Broken pump near the village school");
    await expect(recent.getByTestId("status-badge").first()).toHaveAttribute("data-status", "resolved");
    await expect(page.getByTestId("stat-resolved")).toContainText("1");
    await page.reload();                                                    // persisted, not client state
    await expect(page.getByTestId("recent-complaints")).toContainText("Broken pump near the village school");
  });

  test("an officer of another department can neither see nor change the complaint", async ({ page, request }) => {
    const citizen = await apiCitizen(request);
    const c = await fileComplaint(request, citizen.token, "Cross department probe");
    const other = await staffToken(request, OFFICER2_EMAIL);

    const list = await (await request.get(`${API}/complaints/assigned?limit=200`, { headers: bearer(other) })).json();
    expect(list.items.map((i: any) => i.reference_number)).not.toContain(c.reference_number);
    expect((await request.get(`${API}/complaints/${c.complaint_id}`, { headers: bearer(other) })).status()).toBe(403);
    expect((await request.patch(`${API}/complaints/${c.complaint_id}/status`, { headers: bearer(other), data: { new_status: "assigned" } })).status()).toBe(403);
    expect((await request.post(`${API}/complaints/${c.complaint_id}/assign`, { headers: bearer(other), data: {} })).status()).toBe(403);

    await loginViaUI(page, OFFICER2_EMAIL, STAFF_PASSWORD, "");
    await expect(page).toHaveURL(/\/officer/);
    await expect(page.getByTestId("staff-row").filter({ hasText: c.reference_number })).toHaveCount(0);
  });

  test("another citizen cannot read a private complaint; the state admin can see every department", async ({ request }) => {
    const a = await apiCitizen(request);
    const b = await apiCitizen(request);
    const c = await fileComplaint(request, a.token, "Private complaint of citizen A");
    expect((await request.get(`${API}/complaints/${c.complaint_id}`, { headers: bearer(b.token) })).status()).toBe(403);
    expect((await request.get(`${API}/complaints/assigned`, { headers: bearer(a.token) })).status()).toBe(403);
    expect((await request.patch(`${API}/complaints/${c.complaint_id}/status`, { headers: bearer(b.token), data: { new_status: "assigned" } })).status()).toBe(403);
    const admin = await staffToken(request, ADMIN_EMAIL);
    const all = await (await request.get(`${API}/complaints/assigned?limit=200`, { headers: bearer(admin) })).json();
    expect(all.department_scope).toBeNull();
    expect(all.items.map((i: any) => i.reference_number)).toContain(c.reference_number);
  });

  test("state admin works in the officer console across departments and can assign any officer", async ({ page, request }) => {
    const citizen = await apiCitizen(request);
    const c = await fileComplaint(request, citizen.token, "Admin assignment probe");
    await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "/officer");
    await expect(page.getByTestId("officer-scope")).toHaveText("All departments");
    await page.getByTestId("staff-row").filter({ hasText: c.reference_number }).getByRole("button", { name: c.reference_number }).click();
    const detail = page.getByTestId("complaint-detail");
    const options = await detail.getByLabel("Officer to assign").locator("option").allInnerTexts();
    const label = options.find((o) => o.startsWith("E2E Officer ("));
    expect(label, `options: ${options.join(" | ")}`).toBeTruthy();
    await detail.getByLabel("Officer to assign").selectOption({ label });
    await detail.getByTestId("assign-btn").click();
    await expect(detail.getByTestId("detail-officer")).toHaveText("E2E Officer");
  });
});

test.describe("responsive layout", () => {
  test("dashboard and officer console fit a phone screen", async ({ page, request }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const citizen = await apiCitizen(request);
    await fileComplaint(request, citizen.token, "Mobile layout probe");
    await loginViaUI(page, citizen.email, CITIZEN_PASSWORD, "/dashboard");
    await expect(page.getByTestId("citizen-dashboard")).toBeVisible();
    await expect(page.getByTestId("recent-complaints")).toContainText("Mobile layout probe");
    await noHorizontalScroll(page);
    await page.getByRole("button", { name: "Sign out" }).click();
    await loginViaUI(page, OFFICER_EMAIL, STAFF_PASSWORD, "");
    await expect(page.getByTestId("officer-console")).toBeVisible();
    await noHorizontalScroll(page);
  });
});
