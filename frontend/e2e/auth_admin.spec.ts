import { expect, test } from "@playwright/test";
import {
  ADMIN_EMAIL, API, CITIZEN_PASSWORD, OFFICER_EMAIL, STAFF_PASSWORD, SYSADMIN_EMAIL, apiCitizen, bearer, loginViaUI, registerViaUI, alertBox,
} from "./helpers";

test.describe("citizen authentication", () => {
  test("register signs the citizen in; sign out returns to anonymous", async ({ page }) => {
    await registerViaUI(page, "Asha Kumar");
    await expect(page.getByTestId("user-name")).toHaveText("Asha Kumar");
    await page.getByRole("button", { name: "Sign out" }).click();
    await expect(page.getByRole("link", { name: "Sign In" }).first()).toBeVisible();
  });

  test("session survives a reload", async ({ page }) => {
    await registerViaUI(page, "Persistent User");
    await page.reload();
    await expect(page.getByTestId("user-name")).toHaveText("Persistent User");
  });

  test("wrong password shows a generic error", async ({ page }) => {
    await loginViaUI(page, "nobody@example.com", "wrong-password-1");
    await expect(alertBox(page)).toContainText("Invalid email or password");
  });

  test("weak password is rejected at registration", async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("Full name").fill("Weak");
    await page.getByLabel("Email").fill("weak-user@example.com");
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: "Register" }).click();
    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByTestId("user-name")).toHaveCount(0);
  });

  test("login redirects back to the page that required it", async ({ page, request }) => {
    const c = await apiCitizen(request);
    await page.goto("/complaints");
    await page.getByRole("link", { name: "Sign In" }).last().click();
    await page.getByLabel("Email").fill(c.email);
    await page.getByLabel("Password").fill(CITIZEN_PASSWORD);
    await page.getByRole("button", { name: "Sign In" }).click();
    await expect(page).toHaveURL(/\/complaints/);
    await expect(page.getByLabel(/Subject/)).toBeVisible();
  });
});

test.describe("authorization boundaries", () => {
  test("anonymous visitors are asked to sign in for complaints and admin", async ({ page }) => {
    await page.goto("/complaints");
    await expect(page.getByTestId("login-required")).toBeVisible();
    await page.goto("/admin");
    await expect(page.getByTestId("admin-login-required")).toBeVisible();
  });

  test("a citizen is denied the admin console, and the API agrees", async ({ page, request }) => {
    await registerViaUI(page, "Plain Citizen");
    await page.goto("/admin");
    await expect(page.getByTestId("admin-forbidden")).toBeVisible();
    const c = await apiCitizen(request);
    expect((await request.get(`${API}/admin/overview`, { headers: bearer(c.token) })).status()).toBe(403);
    expect((await request.get(`${API}/admin/overview`)).status()).toBe(401);
  });

  test("an officer is not an administrator", async ({ page }) => {
    await loginViaUI(page, OFFICER_EMAIL, STAFF_PASSWORD, "/admin");
    await expect(page.getByTestId("admin-forbidden")).toBeVisible();
  });

  test("expired or tampered tokens are rejected by the UI session check", async ({ page }) => {
    await page.goto("/");
    await page.evaluate(() => { localStorage.setItem("access_token", "not.a.token"); });
    await page.reload();
    await expect(page.getByRole("link", { name: "Sign In" }).first()).toBeVisible();   // treated as signed out
    expect(await page.evaluate(() => localStorage.getItem("access_token"))).toBeNull();
  });
});

test.describe("administrator console", () => {
  test("admin sees live metrics that match the API, and the verification breakdown", async ({ page, request }) => {
    await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "/admin");
    await expect(page.getByText("Active Schemes")).toBeVisible();
    const login = await request.post(`${API}/auth/login`, { data: { email: ADMIN_EMAIL, password: STAFF_PASSWORD } });
    const token = (await login.json()).access_token;
    const ov = await (await request.get(`${API}/admin/overview`, { headers: bearer(token) })).json();
    await expect(page.getByText("Active Schemes").locator("xpath=..")).toContainText(String(ov.database_stats.schemes));
    const vb = page.getByTestId("verification-breakdown");
    await expect(vb).toContainText("provisional");
    await expect(vb).not.toContainText("official_verified:");   // no record has that status (the explanatory text names it)
  });

  test("audit log panel records sign-ins", async ({ page }) => {
    await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "/admin");
    await page.getByRole("button", { name: "Audit Logs" }).click();
    await expect(page.getByText("LOGIN_SUCCESS").first()).toBeVisible();
  });

  test("state administrators are not offered the SQL workspace (system admin only)", async ({ page }) => {
    await loginViaUI(page, ADMIN_EMAIL, STAFF_PASSWORD, "/admin");
    await expect(page.getByText("Active Schemes")).toBeVisible();
    await expect(page.getByRole("button", { name: "SQL Workspace" })).toHaveCount(0);
  });

  test("SQL workspace (system admin) runs SELECT and refuses mutating statements", async ({ page }) => {
    await loginViaUI(page, SYSADMIN_EMAIL, STAFF_PASSWORD, "/admin");
    await page.getByRole("button", { name: "SQL Workspace" }).click();
    await page.locator("textarea").first().fill("SELECT count(*) AS n FROM administration.district");
    await page.getByRole("button", { name: /Run Query/ }).click();
    await expect(page.getByRole("cell", { name: "38" })).toBeVisible();     // rows render (previously crashed)
    await page.locator("textarea").first().fill("DELETE FROM administration.district");
    await page.getByRole("button", { name: /Run Query/ }).click();
    await expect(page.getByText(/Mutating or unsafe SQL statements are not allowed/)).toBeVisible();
  });
});
