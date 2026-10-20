import { expect, test, type Page } from "@playwright/test";
import { ADMIN_EMAIL, API, CITIZEN_PASSWORD, OFFICER_EMAIL, STAFF_PASSWORD, SYSADMIN_EMAIL, apiCitizen } from "./helpers";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const { ALLOW, SCAN } = require("../audit/i18n-scan");

type Role = "anonymous" | "citizen" | "officer" | "admin" | "sysadmin";
const tokens: Partial<Record<Role, { a: string; r: string }>> = {};

async function login(request: any, role: Role) {
  if (role === "anonymous" || tokens[role]) return tokens[role];
  if (role === "citizen") {
    const c = await apiCitizen(request);
    const body = await (await request.post(`${API}/auth/login`, { data: { email: c.email, password: CITIZEN_PASSWORD } })).json();
    tokens[role] = { a: body.access_token, r: body.refresh_token };
  } else {
    const email = { officer: OFFICER_EMAIL, admin: ADMIN_EMAIL, sysadmin: SYSADMIN_EMAIL }[role];
    const body = await (await request.post(`${API}/auth/login`, { data: { email, password: STAFF_PASSWORD } })).json();
    tokens[role] = { a: body.access_token, r: body.refresh_token };
  }
  return tokens[role];
}

async function open(page: Page, request: any, role: Role, lang: "en" | "ta", url: string) {
  const tk = await login(request, role);
  await page.addInitScript(({ a, r, l }: { a?: string; r?: string; l: string }) => {
    try { localStorage.setItem("lang", l); if (a) { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r ?? ""); } } catch { /* ignore */ }
  }, { a: tk?.a, r: tk?.r, l: lang });
  await page.goto(url);
  await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
}
const scan = (page: Page, lang: "en" | "ta") => page.evaluate(SCAN, { lang, allow: ALLOW });

test.use({ reducedMotion: "reduce" });

// Every route is rendered in both languages; interface text must be in the selected language.
// Allowed exceptions (see audit/i18n-scan.js): lang="en"/lang="ta" subtrees, bilingual scheme/service names, monospace identifiers, brand/acronym allow-list.
const STATES: { name: string; role: Role; url: string }[] = [
  { name: "landing", role: "anonymous", url: "/" },
  { name: "login", role: "anonymous", url: "/login" },
  { name: "register", role: "anonymous", url: "/register" },
  { name: "schemes", role: "anonymous", url: "/schemes" },
  { name: "services", role: "anonymous", url: "/services" },
  { name: "policy documents", role: "anonymous", url: "/documents" },
  { name: "complaints (signed out)", role: "anonymous", url: "/complaints" },
  { name: "complaints (citizen)", role: "citizen", url: "/complaints" },
  { name: "assistant", role: "citizen", url: "/assistant" },
  { name: "citizen dashboard", role: "citizen", url: "/dashboard" },
  { name: "officer console", role: "officer", url: "/officer" },
  { name: "admin console", role: "sysadmin", url: "/admin" },
  { name: "architecture", role: "admin", url: "/database-architecture?tab=architecture" },
  { name: "relational schema", role: "admin", url: "/database-architecture?tab=schema" },
  { name: "not found", role: "anonymous", url: "/no-such-page" },
];

for (const lang of ["ta", "en"] as const) {
  for (const s of STATES) {
    test(`${lang}: ${s.name} shows only ${lang === "ta" ? "Tamil" : "English"} interface text`, async ({ page, request }) => {
      await open(page, request, s.role, lang, s.url);
      await page.waitForTimeout(700);
      expect(await page.evaluate(() => document.documentElement.lang)).toBe(lang);
      expect(await scan(page, lang)).toEqual([]);
    });
  }
}

test.describe("detail pages and states", () => {
  test("scheme and service detail pages (every tab) in Tamil", async ({ page, request }) => {
    const sid = (await (await request.get(`${API}/schemes?page_size=1`)).json()).items[0].scheme_id;
    const vid = (await (await request.get(`${API}/services?page_size=1`)).json()).items[0].service_id;
    for (const url of [`/schemes/${sid}`, `/schemes/${sid}?tab=eligibility`, `/schemes/${sid}?tab=benefits`, `/schemes/${sid}?tab=documents`, `/services/${vid}`]) {
      await open(page, request, "anonymous", "ta", url);
      await page.waitForTimeout(500);
      expect(await scan(page, "ta"), url).toEqual([]);
    }
  });

  test("empty state and error text are translated", async ({ page, request }) => {
    await open(page, request, "anonymous", "ta", "/documents");
    await page.getByTestId("document-search").fill("zzzz-no-such-document");
    await page.getByRole("button", { name: "தேடு" }).click();
    await expect(page.getByTestId("empty-state")).toContainText("பொருந்தும் ஆவணங்கள் இல்லை");
    await open(page, request, "anonymous", "ta", "/complaints");
    await page.getByRole("tab").nth(1).click();
    await page.getByPlaceholder(/MYG-2026-000001/).fill("MYG-2026-999999");
    await page.getByRole("button", { name: "கண்காணி" }).click();
    await expect(page.getByRole("alert").filter({ hasText: "கிடைக்கவில்லை" })).toBeVisible();
    expect(await scan(page, "ta")).toEqual([]);
  });

  test("language choice survives navigation and reload", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "தமிழ்" }).first().click();
    await page.goto("/services");
    await expect(page.locator("html")).toHaveAttribute("lang", "ta");
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("lang", "ta");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("இ-சேவை");
  });

  test("scheme and service names always appear in both languages", async ({ page, request }) => {
    const schemes = (await (await request.get(`${API}/schemes?page_size=50`)).json()).items;
    const services = (await (await request.get(`${API}/services?page_size=50`)).json()).items;
    expect(schemes.every((s: any) => s.name && s.name_ta)).toBe(true);
    expect(services.every((s: any) => s.name && s.name_ta)).toBe(true);
    for (const lang of ["en", "ta"] as const) {
      await open(page, request, "anonymous", lang, "/schemes");
      const card = page.getByTestId("scheme-card").first();
      await expect(card.getByTestId("scheme-secondary-name")).not.toBeEmpty();
      const text = await card.innerText();
      expect(/[஀-௿]/.test(text) && /[A-Za-z]{3}/.test(text)).toBe(true);   // Tamil and English name both present
      await open(page, request, "anonymous", lang, "/services");
      await expect(page.getByTestId("service-card").first().getByTestId("service-secondary-name")).not.toBeEmpty();
    }
  });
});
