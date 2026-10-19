/**
 * Browser audit sweep: visits every route as every role at three viewport widths and records what actually happens.
 *
 *   node audit/sweep.js [outDir]        (env: WEB=http://localhost:3000 API=http://localhost:8000 DEMO_PASSWORD=...)
 *
 * Needs the running demo stack (see docs/demo.md). Writes <outDir>/route_sweep.json and route_inventory.csv.
 * It only reads pages (GET navigation); it changes no data.
 */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const WEB = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const PASSWORD = process.env.DEMO_PASSWORD || "Demo@12345";
const OUT = process.argv[2] || path.join(__dirname, "out");
fs.mkdirSync(OUT, { recursive: true });

const ROLES = ["anonymous", "citizen", "officer", "officer2", "deptadmin", "admin", "sysadmin"];
const VIEWPORTS = { desktop: { width: 1440, height: 900 }, tablet: { width: 820, height: 1100 }, mobile: { width: 390, height: 844 } };
// Who is supposed to see the real page (everything else must be redirected or refused). "*" = everyone.
const EXPECT = {
  "/": "*", "/login": "*", "/register": "*", "/schemes": "*", "/schemes/:id": "*", "/services": "*", "/documents": "*",
  "/complaints": "*",                      // public tabs (track); filing needs sign-in and says so
  "/assistant": "*",
  "/dashboard": ["citizen"],
  "/officer": ["officer", "officer2", "deptadmin", "admin", "sysadmin"],
  "/admin": ["admin", "sysadmin"],
  "/database-architecture": ["admin", "sysadmin"],
  "/this-page-does-not-exist": [],
};

async function token(email) {
  const r = await fetch(`${API}/api/v1/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email, password: PASSWORD }) });
  if (!r.ok) throw new Error(`login ${email}: ${r.status}`);
  const b = await r.json();
  return { access: b.access_token, refresh: b.refresh_token };
}

async function inspect(page) {
  return page.evaluate(async () => {
    const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
    const name = (el) => (el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || el.textContent || el.getAttribute("title") || "").trim();
    const links = [...document.querySelectorAll("a")].filter(vis);
    const buttons = [...document.querySelectorAll("button")].filter(vis);
    const inputs = [...document.querySelectorAll("input,select,textarea")].filter((e) => vis(e) && e.type !== "hidden");
    const labelled = (el) => !!(el.getAttribute("aria-label") || el.getAttribute("aria-labelledby") || (el.id && document.querySelector(`label[for="${CSS.escape(el.id)}"]`)) || el.closest("label") || el.getAttribute("title"));
    const imgs = [...document.images].filter(vis);
    const headings = [...document.querySelectorAll("h1,h2,h3")].map((h) => `${h.tagName}:${h.textContent.trim().slice(0, 60)}`);
    const levels = headings.map((h) => +h[1]);
    let skipped = 0; for (let i = 1; i < levels.length; i++) if (levels[i] - levels[i - 1] > 1) skipped++;
    const tw = getComputedStyle(document.body).backgroundColor;
    return {
      title: document.title, h1: (document.querySelector("h1")?.textContent || "").trim().slice(0, 80),
      h1_count: document.querySelectorAll("h1").length, heading_skips: skipped,
      overflow_px: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      links: links.length, dead_links: links.filter((a) => { const h = a.getAttribute("href"); return !h || h === "#" || h.startsWith("javascript:"); }).map((a) => name(a).slice(0, 40)),
      links_without_name: links.filter((a) => !name(a) && !a.querySelector("img[alt]")).length,
      buttons: buttons.length, buttons_without_name: buttons.filter((b) => !name(b)).length,
      inputs: inputs.length, inputs_without_label: inputs.filter((i) => !labelled(i)).map((i) => i.id || i.name || i.placeholder || i.tagName).slice(0, 5),
      images: imgs.length, broken_images: imgs.filter((i) => !i.complete || i.naturalWidth === 0).length,
      tailwind_applied: tw !== "rgba(0, 0, 0, 0)", font: getComputedStyle(document.body).fontFamily.split(",")[0].trim(),
      body_text: document.body.innerText.replace(/\s+/g, " ").trim().slice(0, 200),
      mentions_login_required: /sign in|log in/i.test(document.body.innerText) && !document.querySelector("[data-testid=user-name]"),
      placeholder_text: /lorem ipsum|todo|fixme|undefined|\[object Object\]|NaN/.test(document.body.innerText),
    };
  });
}

(async () => {
  const schemes = await (await fetch(`${API}/api/v1/schemes?page_size=1`)).json();
  const schemeId = schemes.items[0].scheme_id;
  const ROUTES = Object.keys(EXPECT).map((r) => ({ pattern: r, url: r.replace(":id", schemeId) }));
  const tokens = { anonymous: null };
  const emails = { citizen: "citizen", officer: "officer", officer2: "officer2", deptadmin: "deptadmin", admin: "admin", sysadmin: "sysadmin" };
  for (const [role, local] of Object.entries(emails)) tokens[role] = await token(`${local}@demo.example`);

  const browser = await chromium.launch();
  const rows = [];
  for (const role of ROLES) {
    for (const route of ROUTES) {
      const row = { role, route: route.pattern, expected_access: EXPECT[route.pattern] === "*" ? "everyone" : EXPECT[route.pattern].join("|") || "nobody (404)" };
      for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
        const ctx = await browser.newContext({ viewport: vp, reducedMotion: "reduce" });
        if (tokens[role]) await ctx.addInitScript(({ a, r }) => { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r); }, { a: tokens[role].access, r: tokens[role].refresh });
        const page = await ctx.newPage();
        const consoleErrors = [], pageErrors = [], failed = [];
        page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 160)); });
        page.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 160)));
        page.on("requestfailed", (r) => failed.push(`${r.method()} ${r.url().replace(WEB, "").replace(API, "")} ${r.failure()?.errorText}`));
        page.on("response", (r) => { if (r.status() >= 400 && !r.url().includes("/_next/")) failed.push(`${r.request().method()} ${r.url().replace(WEB, "").replace(API, "")} -> ${r.status()}`); });
        let status = 0;
        try {
          const resp = await page.goto(WEB + route.url, { waitUntil: "load", timeout: 30000 });
          status = resp ? resp.status() : 0;
          await page.waitForLoadState("networkidle", { timeout: 8000 }).catch(() => {});
          await page.waitForTimeout(1200);
          const info = await inspect(page);
          const finalPath = new URL(page.url()).pathname + new URL(page.url()).search.replace(/^\?$/, "");
          if (vpName === "desktop") Object.assign(row, { http_status: status, final_path: finalPath, redirected: finalPath.split("?")[0] !== route.url.split("?")[0], ...info,
            console_errors: [...new Set(consoleErrors)].join(" | "), page_errors: pageErrors.join(" | "), failed_requests: [...new Set(failed)].join(" | ") });
          row[`overflow_${vpName}`] = info.overflow_px;
          row[`console_errors_${vpName}`] = [...new Set(consoleErrors)].length + pageErrors.length;
          if (vpName !== "desktop") row[`failed_${vpName}`] = [...new Set(failed)].length;
          if (role === "citizen" || role === "admin" || role === "anonymous") await page.screenshot({ path: path.join(OUT, `${role}_${route.pattern.replace(/[^a-z]+/gi, "_")}_${vpName}.png`), fullPage: false }).catch(() => {});
        } catch (e) {
          row[`error_${vpName}`] = String(e).slice(0, 160);
        }
        await ctx.close();
      }
      rows.push(row);
      process.stdout.write(`${role.padEnd(10)} ${route.pattern.padEnd(26)} -> ${row.final_path ?? "ERR"}  ${row.http_status ?? ""}\n`);
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "route_sweep.json"), JSON.stringify(rows, null, 1));
  const cols = ["role", "route", "expected_access", "http_status", "final_path", "redirected", "title", "h1", "h1_count", "heading_skips", "links", "dead_links", "links_without_name", "buttons", "buttons_without_name",
    "inputs", "inputs_without_label", "images", "broken_images", "tailwind_applied", "font", "overflow_desktop", "overflow_tablet", "overflow_mobile", "console_errors", "page_errors", "failed_requests", "placeholder_text", "body_text"];
  const esc = (v) => `"${String(Array.isArray(v) ? v.join("; ") : v ?? "").replace(/"/g, '""')}"`;
  fs.writeFileSync(path.join(OUT, "route_inventory.csv"), [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n"));
  console.log(`\nwrote ${rows.length} rows to ${OUT}`);
})().catch((e) => { console.error("FAILED", e); process.exit(1); });
