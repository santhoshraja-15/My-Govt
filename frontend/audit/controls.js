/**
 * Control audit: lists every visible interactive control on each page and clicks each one (fresh page load per control),
 * recording whether ANYTHING happened: URL change, DOM mutation, new network request, or a dialog. A control with no effect
 * is a dead-control candidate to review by hand.
 *
 *   node audit/controls.js [outDir]        (env: WEB, API, DEMO_PASSWORD, ONLY=route1,route2, ROLE=citizen)
 *
 * Read-only intent: it clicks buttons/links/tabs/checkboxes but never types; form submissions are sent empty so they only
 * trigger validation. Run against a disposable demo database.
 */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const WEB = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const PASSWORD = process.env.DEMO_PASSWORD || "Demo@12345";
const OUT = process.argv[2] || path.join(__dirname, "out");
fs.mkdirSync(OUT, { recursive: true });

const PLAN = [
  { role: "anonymous", routes: ["/", "/login", "/register", "/schemes", "/services", "/documents", "/complaints", "/assistant"] },
  { role: "citizen", routes: ["/dashboard", "/complaints", "/assistant", "/schemes", "/services"] },
  { role: "officer", routes: ["/officer"] },
  { role: "deptadmin", routes: ["/officer"] },
  { role: "admin", routes: ["/admin", "/database-architecture", "/database-architecture?tab=er", "/database-architecture?tab=schema", "/database-architecture?tab=implementation", "/database-architecture?tab=advanced"] },
];
const SKIP_NAMES = /^(sign out|logout)$/i;

async function tokenFor(role) {
  if (role === "anonymous") return null;
  const r = await fetch(`${API}/api/v1/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${role}@demo.example`, password: PASSWORD }) });
  const b = await r.json();
  return { a: b.access_token, r: b.refresh_token };
}

const LIST = `(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none" && !el.disabled; };
  const sel = 'button, a[href], [role="tab"], summary, input[type="checkbox"], input[type="radio"], select';
  const out = [], seen = new Set();
  document.querySelectorAll(sel).forEach((el, i) => {
    if (!vis(el)) return;
    const name = (el.getAttribute("aria-label") || el.textContent || el.getAttribute("title") || el.id || el.tagName).replace(/\\s+/g, " ").trim().slice(0, 50);
    const key = el.tagName + "|" + name + "|" + (el.getAttribute("href") || "") + "|" + (el.closest("[data-testid]")?.getAttribute("data-testid") || "");
    if (seen.has(key)) return; seen.add(key);
    el.setAttribute("data-audit-idx", String(out.length));
    out.push({ idx: out.length, tag: el.tagName.toLowerCase(), name, href: el.getAttribute("href") || "", type: el.getAttribute("type") || "" });
  });
  return out;
})()`;

(async () => {
  const browser = await chromium.launch();
  const rows = [];
  for (const { role, routes } of PLAN) {
    if (process.env.ROLE && process.env.ROLE !== role) continue;
    const tok = await tokenFor(role);
    for (const route of routes) {
      if (process.env.ONLY && !process.env.ONLY.split(",").includes(route)) continue;
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
      if (tok) await ctx.addInitScript(({ a, r }) => { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r); }, tok);
      const page = await ctx.newPage();
      let requests = 0, dialogs = 0;
      page.on("request", (r) => { if (!r.url().includes("_rsc") && !r.url().includes("/_next/")) requests++; });
      page.on("dialog", (d) => { dialogs++; d.dismiss().catch(() => {}); });
      const open = async () => {
        await page.goto(WEB + route, { waitUntil: "load" });
        await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
        await page.waitForTimeout(350);
      };
      await open();
      const controls = await page.evaluate(LIST);
      for (const c of controls.slice(0, 80)) {
        if (SKIP_NAMES.test(c.name)) { rows.push({ role, route, ...c, effect: "skipped", detail: "sign-out" }); continue; }
        await open();
        await page.evaluate(LIST);
        requests = 0; dialogs = 0;
        await page.evaluate(() => { window.__mut = 0; new MutationObserver((m) => { window.__mut += m.length; }).observe(document.body, { childList: true, subtree: true, attributes: true, characterData: true }); });
        const before = page.url();
        const el = page.locator(`[data-audit-idx="${c.idx}"]`).first();
        let note = "";
        try {
          if (c.tag === "select") {
            const opts = await el.locator("option").evaluateAll((o) => o.map((x) => x.value));
            const cur = await el.inputValue();
            const other = opts.find((v) => v !== cur);
            if (other === undefined) { note = "single option"; } else await el.selectOption(other, { timeout: 3000 });
          } else await el.click({ timeout: 3000, force: true });
        } catch (e) { note = "click failed: " + String(e).slice(0, 80).split(" ").join(" "); }
        await page.waitForTimeout(450);
        const mut = await page.evaluate(() => window.__mut || 0).catch(() => -1);
        const changedUrl = page.url() !== before;
        const effect = note.startsWith("click failed") ? "error" : (changedUrl || mut > 0 || requests > 0 || dialogs > 0) ? "ok" : "NO EFFECT";
        rows.push({ role, route, ...c, effect, detail: [changedUrl ? `navigated:${new URL(page.url()).pathname}` : "", mut > 0 ? `dom:${mut}` : "", requests ? `req:${requests}` : "", dialogs ? "dialog" : "", note].filter(Boolean).join(" ") });
      }
      await ctx.close();
      const bad = rows.filter((r) => r.route === route && r.role === role && (r.effect === "NO EFFECT" || r.effect === "error"));
      console.log(`${role.padEnd(10)} ${route.padEnd(44)} controls=${controls.length} noEffect/error=${bad.length}${bad.length ? "  -> " + bad.map((b) => `${b.tag}:"${b.name}"`).join(", ").slice(0, 200) : ""}`);
    }
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "control_audit.json"), JSON.stringify(rows, null, 1));
  const cols = ["role", "route", "tag", "type", "name", "href", "effect", "detail"];
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  fs.writeFileSync(path.join(OUT, "control_audit.csv"), [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n"));
  console.log(`\n${rows.length} controls tested; ${rows.filter((r) => r.effect === "NO EFFECT").length} with no effect; ${rows.filter((r) => r.effect === "error").length} errors`);
})().catch((e) => { console.error("FAILED", e); process.exit(1); });
