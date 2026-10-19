/**
 * Screenshots for the project report/PPT. Read-only (nothing is submitted). Needs the running demo stack.
 *   node audit/submission_shots.js ../docs/submission/images
 */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const WEB = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_PASSWORD || "Demo@12345";
const OUT = path.resolve(process.argv[2] || "shots");
fs.mkdirSync(OUT, { recursive: true });

async function tokenFor(role) {
  if (role === "anonymous") return null;
  const r = await fetch(`${API}/api/v1/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${role}@demo.example`, password: PASSWORD }) });
  const b = await r.json();
  return { a: b.access_token, r: b.refresh_token };
}

const SHOTS = [
  { f: "01_landing", role: "anonymous", url: "/" },
  { f: "02_schemes", role: "anonymous", url: "/schemes", prep: async (p) => { await p.getByTestId("scheme-card").first().waitFor(); } },
  { f: "03_eligibility", role: "anonymous", url: "/schemes", prep: async (p) => {
      await p.getByLabel("Search schemes").fill("Magalir"); await p.getByRole("button", { name: "Search", exact: true }).click();
      await p.getByTestId("scheme-card").first().click(); await p.getByTestId("check-my-eligibility").click(); await p.getByTestId("eligibility-form").waitFor(); } },
  { f: "04_services", role: "anonymous", url: "/services" },
  { f: "05_documents", role: "anonymous", url: "/documents" },
  { f: "06_citizen_dashboard", role: "citizen", url: "/dashboard" },
  { f: "07_file_complaint", role: "citizen", url: "/complaints", prep: async (p) => { await p.getByRole("tab", { name: "File Complaint" }).click(); } },
  { f: "08_my_complaints", role: "citizen", url: "/complaints", prep: async (p) => { await p.getByRole("tab", { name: /My Complaints/ }).click().catch(() => {}); } },
  { f: "09_assistant", role: "citizen", url: "/assistant" },
  { f: "10_officer_console", role: "officer", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().waitFor(); } },
  { f: "11_officer_detail", role: "officer", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().getByRole("button").first().click(); await p.getByTestId("complaint-detail").waitFor(); await p.waitForTimeout(600); } },
  { f: "12_admin_overview", role: "admin", url: "/admin" },
  { f: "13_admin_verification", role: "admin", url: "/admin", prep: async (p) => { await p.getByRole("button", { name: "Verification Queue" }).click(); await p.waitForTimeout(900); } },
  { f: "14_admin_schema_explorer", role: "admin", url: "/admin", prep: async (p) => { await p.getByRole("button", { name: "Schema Explorer" }).click(); await p.waitForTimeout(900); } },
  { f: "15_arch_architecture", role: "admin", url: "/database-architecture?tab=architecture", full: true },
  { f: "16_arch_er", el: "er-diagram", big: true, role: "admin", url: "/database-architecture?tab=er", prep: async (p) => { await p.getByTestId("er-node").first().waitFor(); await p.getByTestId("er-fit").click(); await p.waitForTimeout(800); } },
  { f: "17_arch_er_focus", el: "er-diagram", big: true, role: "admin", url: "/database-architecture?tab=er", prep: async (p) => {
      await p.getByTestId("er-node").first().waitFor();
      await p.getByTestId("er-search").fill("complaints.complaint"); await p.waitForTimeout(500);
      await p.locator('[data-testid="er-node"][data-table="complaints.complaint"]').first().click({ force: true });
      await p.getByTestId("er-focus").check(); await p.waitForTimeout(900); await p.getByTestId("er-fit").click(); await p.waitForTimeout(700); } },
  { f: "18_arch_schema", role: "admin", url: "/database-architecture?tab=schema", prep: async (p) => { await p.getByTestId("relation-list").waitFor(); } },
  { f: "19_arch_implementation", role: "admin", url: "/database-architecture?tab=implementation", prep: async (p) => { await p.getByTestId("impl-table-list").waitFor(); } },
  { f: "20_arch_advanced", role: "admin", url: "/database-architecture?tab=advanced", full: true },
];

(async () => {
  const browser = await chromium.launch();
  const tokens = {};
  let ok = 0;
  for (const s of SHOTS) {
    tokens[s.role] ??= await tokenFor(s.role);
    const ctx = await browser.newContext({ viewport: s.big ? { width: 1900, height: 1500 } : { width: 1440, height: 900 }, reducedMotion: "reduce" });
    if (tokens[s.role]) await ctx.addInitScript(({ a, r }) => { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r); }, tokens[s.role]);
    const page = await ctx.newPage();
    try {
      await page.goto(WEB + s.url, { waitUntil: "load" });
      await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
      await page.waitForTimeout(700);
      if (s.prep) await s.prep(page);
      await page.waitForTimeout(500);
      const target = s.el ? page.getByTestId(s.el) : page;
      await target.screenshot({ path: path.join(OUT, s.f + ".png"), ...(s.el ? {} : { fullPage: !!s.full }) });
      console.log("ok  ", s.f); ok++;
    } catch (e) { console.log("FAIL", s.f, String(e).split("\n")[0].slice(0, 110)); }
    await ctx.close();
  }
  await browser.close();
  console.log(`${ok}/${SHOTS.length} screenshots`);
})();
