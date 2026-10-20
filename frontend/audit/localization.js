/**
 * Localization audit: renders every route/state in Tamil and in English and reports interface text that is in the wrong language.
 *
 *   node audit/localization.js [outDir]       (env: WEB, API, DEMO_PASSWORD)
 *
 * Tamil mode  : every visible text node, placeholder, aria-label, title and alt must contain no Latin words, except
 *               - subtrees marked lang="en" (government-supplied prose that has no Tamil version, shown as-is),
 *               - code / pre / script / style,
 *               - an allow-list of brand names, acronyms and technical identifiers.
 * English mode: no Tamil characters outside lang="ta" subtrees and the bilingual-name elements (scheme/service names).
 * Needs the running demo stack. Read-only.
 */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const WEB = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://127.0.0.1:8000";
const PASSWORD = process.env.DEMO_PASSWORD || "Demo@12345";
const OUT = process.argv[2] || path.join(__dirname, "out");
fs.mkdirSync(OUT, { recursive: true });

const { ALLOW, SCAN } = require("./i18n-scan");

async function tokenFor(role) {
  if (role === "anonymous") return null;
  const r = await fetch(`${API}/api/v1/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${role}@demo.example`, password: PASSWORD }) });
  const b = await r.json();
  return { a: b.access_token, r: b.refresh_token };
}

async function firstId(kind) {
  const r = await fetch(`${API}/api/v1/${kind}?page_size=1`);
  return (await r.json()).items[0][kind === "schemes" ? "scheme_id" : "service_id"];
}

(async () => {
  const schemeId = await firstId("schemes");
  const serviceId = await firstId("services");
  const STATES = [
    { n: "Landing", role: "anonymous", url: "/" },
    { n: "Login", role: "anonymous", url: "/login" },
    { n: "Register", role: "anonymous", url: "/register" },
    { n: "Schemes list", role: "anonymous", url: "/schemes" },
    { n: "Schemes filters", role: "anonymous", url: "/schemes", prep: async (p) => { await p.getByTestId("scheme-card").first().waitFor(); await p.locator('button[aria-expanded]').first().click(); } },
    { n: "Scheme detail", role: "anonymous", url: `/schemes/${schemeId}` },
    { n: "Scheme eligibility", role: "anonymous", url: `/schemes/${schemeId}?tab=eligibility` },
    { n: "Scheme benefits", role: "anonymous", url: `/schemes/${schemeId}?tab=benefits` },
    { n: "Scheme documents", role: "anonymous", url: `/schemes/${schemeId}?tab=documents` },
    { n: "Services list", role: "anonymous", url: "/services" },
    { n: "Service detail", role: "anonymous", url: `/services/${serviceId}` },
    { n: "Policy documents", role: "anonymous", url: "/documents" },
    { n: "Policy documents (details open)", role: "anonymous", url: "/documents", prep: async (p) => { await p.getByTestId("doc-details-toggle").first().click(); } },
    { n: "Complaints (citizen) file", role: "citizen", url: "/complaints" },
    { n: "Complaints track", role: "citizen", url: "/complaints", prep: async (p) => { await p.getByRole("tab").nth(1).click(); } },
    { n: "Complaints mine", role: "citizen", url: "/complaints", prep: async (p) => { await p.getByRole("tab").nth(2).click(); await p.waitForTimeout(800); } },
    { n: "Complaints (signed out)", role: "anonymous", url: "/complaints" },
    { n: "Assistant", role: "citizen", url: "/assistant" },
    { n: "Citizen dashboard", role: "citizen", url: "/dashboard" },
    { n: "Officer console", role: "officer", url: "/officer" },
    { n: "Officer detail", role: "officer", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().waitFor(); await p.getByTestId("staff-row").first().getByRole("button").first().click(); await p.getByTestId("complaint-detail").waitFor(); await p.waitForTimeout(500); } },
    { n: "Department admin console", role: "deptadmin", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().waitFor(); } },
    ...["Overview", "Complaints", "Department Performance", "Verification Queue", "Schema Explorer", "SQL Workspace", "Datasets", "Data Quality", "Audit Logs", "Knowledge Graph"].map((name, i) => ({
      n: `Admin: ${name}`, role: "sysadmin", url: "/admin",
      prep: async (p) => { if (i > 0) await p.locator("aside nav button").nth(i).click(); await p.waitForTimeout(1200); } })),
    { n: "Architecture", role: "admin", url: "/database-architecture?tab=architecture" },
    { n: "ER diagram", role: "admin", url: "/database-architecture?tab=er", prep: async (p) => { await p.getByTestId("er-node").first().waitFor(); await p.getByTestId("er-node").first().click({ force: true }); await p.waitForTimeout(800); } },
    { n: "Relational schema", role: "admin", url: "/database-architecture?tab=schema", prep: async (p) => { await p.getByTestId("relation-list").waitFor(); await p.waitForTimeout(800); } },
    { n: "Implementation", role: "admin", url: "/database-architecture?tab=implementation", prep: async (p) => { await p.getByTestId("impl-table-list").waitFor(); await p.locator('[data-testid="impl-table-list"] button').first().click(); await p.waitForTimeout(1200); } },
    { n: "Advanced concepts", role: "admin", url: "/database-architecture?tab=advanced", prep: async (p) => { await p.getByTestId("concept-card").first().waitFor(); } },
    { n: "404", role: "anonymous", url: "/this-page-does-not-exist" },
  ];

  const browser = await chromium.launch();
  const tokens = {};
  const report = [];
  for (const lang of ["ta", "en"]) {
    for (const s of STATES) {
      tokens[s.role] ??= await tokenFor(s.role);
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce" });
      await ctx.addInitScript(({ a, r, l }) => { try { localStorage.setItem("lang", l); if (a) { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r); } } catch (e) {} }, { a: tokens[s.role]?.a, r: tokens[s.role]?.r, l: lang });
      const page = await ctx.newPage();
      const missing = [];
      page.on("console", (m) => { if (m.type() === "warning" && m.text().includes("[i18n] missing")) missing.push(m.text()); });
      let bad = [], err = null;
      try {
        await page.goto(WEB + s.url, { waitUntil: "load" });
        await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
        await page.waitForTimeout(500);
        if (s.prep) await s.prep(page);
        await page.waitForTimeout(500);
        const htmlLang = await page.evaluate(() => document.documentElement.lang);
        bad = await page.evaluate(SCAN, { lang, allow: ALLOW });
        if (htmlLang !== lang) bad.push({ where: "html", text: `document lang is ${htmlLang}, expected ${lang}` });
      } catch (e) { err = String(e).split("\n")[0].slice(0, 160); }
      report.push({ lang, state: s.n, url: s.url, role: s.role, issues: bad, missing_keys: missing, error: err });
      console.log(`${lang} ${s.n.padEnd(34)} ${err ? "ERROR " + err : bad.length + " issue(s)"}${missing.length ? ` + ${missing.length} missing keys` : ""}`);
      await ctx.close();
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "localization_audit.json"), JSON.stringify(report, null, 1));
  const total = report.reduce((a, r) => a + r.issues.length, 0);
  console.log(`\n${report.length} state renders, ${total} issues, ${report.filter((r) => r.error).length} errors`);
})().catch((e) => { console.error("FAILED", e); process.exit(1); });
