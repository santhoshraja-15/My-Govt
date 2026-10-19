import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8010/api/v1";
export const ADMIN_EMAIL = "e2e-admin@example.com";
export const OFFICER_EMAIL = "e2e-officer@example.com";
export const SYSADMIN_EMAIL = "e2e-sysadmin@example.com";
export const DEPTADMIN_EMAIL = "e2e-deptadmin@example.com";
// Fixture credentials for the disposable E2E database only (see backend/scripts/e2e_env.py).
export const STAFF_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? "E2e-test-pass-1";
export const CITIZEN_PASSWORD = "Citizen-test-pass-1";

export function uniqueEmail(prefix = "citizen") {
  return `${prefix}-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}@example.com`;
}

export async function registerViaUI(page: Page, name = "Test Citizen") {
  const email = uniqueEmail();
  await page.goto("/register");
  await page.getByLabel("Full name").fill(name);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(CITIZEN_PASSWORD);
  await page.getByRole("button", { name: "Register" }).click();
  await expect(page.getByTestId("user-name")).toHaveText(name);
  return email;
}

export async function loginViaUI(page: Page, email: string, password: string, next = "/") {
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();
}

/** Register and log in through the API (no UI) and return a bearer token. */
export async function apiCitizen(request: APIRequestContext) {
  const email = uniqueEmail("api");
  const reg = await request.post(`${API}/auth/register`, { data: { email, password: CITIZEN_PASSWORD, full_name: "API Citizen" } });
  expect(reg.status()).toBe(201);
  const login = await request.post(`${API}/auth/login`, { data: { email, password: CITIZEN_PASSWORD } });
  const body = await login.json();
  return { email, token: body.access_token as string, citizenId: body.user.citizen_id as string };
}

export const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });

/** In-page alert, excluding Next.js route announcer which also has role="alert". */
export const alertBox = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');
