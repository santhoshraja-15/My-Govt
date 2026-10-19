/**
 * Field audit: for every form state in the application, lists each input/select/textarea with what a user (and assistive
 * technology) actually gets: accessible name, type, required/min/max/length constraints, initial value, options, and whether
 * the control is labelled by a real label or only by a placeholder. Also visits every admin panel and records whether it
 * loaded data or showed an error.
 *
 *   node audit/fields.js [outDir]       (env: WEB, API, DEMO_PASSWORD)
 *
 * Needs the running demo stack. Read-only: it opens screens and tabs but submits nothing.
 */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const WEB = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const PASSWORD = process.env.DEMO_PASSWORD || "Demo@12345";
const OUT = process.argv[2] || path.join(__dirname, "out");
fs.mkdirSync(OUT, { recursive: true });

async function tokenFor(role) {
  if (role === "anonymous") return null;
  const r = await fetch(`${API}/api/v1/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${role}@demo.example`, password: PASSWORD }) });
  const b = await r.json();
  return { a: b.access_token, r: b.refresh_token };
}

const SCAN = `(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none"; };
  const text = (el) => (el ? el.textContent.replace(/\\s+/g, " ").trim() : "");
  const nameOf = (el) => {
    if (el.getAttribute("aria-label")) return { name: el.getAttribute("aria-label"), source: "aria-label" };
    const lb = el.getAttribute("aria-labelledby");
    if (lb) return { name: lb.split(" ").map((i) => text(document.getElementById(i))).join(" "), source: "aria-labelledby" };
    if (el.id) { const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]'); if (l) return { name: text(l), source: "label[for]" }; }
    const wrap = el.closest("label"); if (wrap) return { name: text(wrap), source: "wrapping label" };
    if (el.getAttribute("title")) return { name: el.getAttribute("title"), source: "title" };
    if (el.getAttribute("placeholder")) return { name: el.getAttribute("placeholder"), source: "PLACEHOLDER ONLY" };
    return { name: "", source: "NONE" };
  };
  return [...document.querySelectorAll("input, select, textarea")].filter((e) => vis(e) && e.type !== "hidden").map((el) => {
    const n = nameOf(el);
    return {
      tag: el.tagName.toLowerCase(), type: el.type || "", name: n.name.slice(0, 80), name_source: n.source, id: el.id || "", testid: el.getAttribute("data-testid") || "",
      required: el.required || el.getAttribute("aria-required") === "true", min: el.getAttribute("min") || "", max: el.getAttribute("max") || "",
      minlength: el.getAttribute("minlength") || "", maxlength: el.getAttribute("maxlength") || "", pattern: el.getAttribute("pattern") || "",
      autocomplete: el.getAttribute("autocomplete") || "", placeholder: el.getAttribute("placeholder") || "", disabled: !!el.disabled, readonly: !!el.readOnly,
      initial: el.type === "checkbox" || el.type === "radio" ? String(el.checked) : (el.tagName === "SELECT" ? (el.selectedOptions[0] ? text(el.selectedOptions[0]) : "") : (el.value || "")).slice(0, 60),
      options: el.tagName === "SELECT" ? [...el.options].map((o) => text(o)).slice(0, 14).join(" | ") : "",
      described_by: el.getAttribute("aria-describedby") || "",
    };
  });
})()`;

const STATES = [
  { role: "anonymous", label: "Login form", url: "/login" },
  { role: "anonymous", label: "Registration form", url: "/register" },
  { role: "anonymous", label: "Landing search", url: "/" },
  { role: "anonymous", label: "Scheme search + filters", url: "/schemes", prep: async (p) => { await p.getByRole("button", { name: "Toggle filters" }).click(); } },
  { role: "anonymous", label: "Eligibility checker (scheme with rules)", url: "/schemes", prep: async (p) => {
      await p.getByLabel("Search schemes").fill("Magalir"); await p.getByRole("button", { name: "Search", exact: true }).click();
      await p.getByTestId("scheme-card").first().click(); await p.getByTestId("check-my-eligibility").click(); await p.getByTestId("eligibility-form").waitFor(); } },
  { role: "anonymous", label: "Service search", url: "/services" },
  { role: "anonymous", label: "Document search + filters", url: "/documents" },
  { role: "anonymous", label: "Complaint tracking", url: "/complaints", prep: async (p) => { await p.getByRole("tab", { name: "Track Status" }).click(); } },
  { role: "citizen", label: "Complaint filing form", url: "/complaints", prep: async (p) => { await p.getByRole("tab", { name: "File Complaint" }).click(); } },
  { role: "citizen", label: "Citizen assistant", url: "/assistant" },
  { role: "officer", label: "Officer console filters", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().waitFor(); } },
  { role: "officer", label: "Officer complaint detail (remarks)", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().getByRole("button").first().click(); await p.getByTestId("complaint-detail").waitFor(); await p.waitForTimeout(500); } },
  { role: "deptadmin", label: "Department admin assignment", url: "/officer", prep: async (p) => { await p.getByTestId("staff-row").first().getByRole("button").first().click(); await p.getByTestId("complaint-detail").waitFor(); await p.waitForTimeout(500); } },
  { role: "admin", label: "Admin: complaints filters", url: "/admin", prep: async (p) => { await p.getByRole("button", { name: "Complaints" }).first().click(); await p.waitForTimeout(800); } },
  { role: "sysadmin", label: "Admin: SQL workspace", url: "/admin", prep: async (p) => { await p.getByRole("button", { name: "SQL Workspace" }).click(); await p.waitForTimeout(600); } },
  { role: "admin", label: "Admin: schema explorer", url: "/admin", prep: async (p) => { await p.getByRole("button", { name: "Schema Explorer" }).click(); await p.waitForTimeout(800); } },
  { role: "admin", label: "Architecture: ER controls", url: "/database-architecture?tab=er", prep: async (p) => { await p.getByTestId("er-node").first().waitFor(); } },
  { role: "admin", label: "Architecture: relational schema filters", url: "/database-architecture?tab=schema", prep: async (p) => { await p.getByTestId("relation-list").waitFor(); } },
  { role: "admin", label: "Architecture: implementation browser", url: "/database-architecture?tab=implementation", prep: async (p) => { await p.getByTestId("impl-table-list").waitFor(); } },
];

const ADMIN_PANELS = ["Overview", "Complaints", "Department Performance", "Verification Queue", "Schema Explorer", "SQL Workspace", "Datasets", "Data Quality", "Audit Logs", "Knowledge Graph"];

(async () => {
  const browser = await chromium.launch();
  const fields = [], panels = [];
  const tokens = {};
  for (const s of STATES) {
    tokens[s.role] ??= await tokenFor(s.role);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
    if (tokens[s.role]) await ctx.addInitScript(({ a, r }) => { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r); }, tokens[s.role]);
    const page = await ctx.newPage();
    try {
      await page.goto(WEB + s.url, { waitUntil: "load" });
      await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
      await page.waitForTimeout(500);
      if (s.prep) await s.prep(page);
      await page.waitForTimeout(400);
      const list = await page.evaluate(SCAN);
      const shown = new URL(page.url()).pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/, ":id");
      for (const f of list) fields.push({ page: shown, state: s.label, role: s.role, ...f });
      console.log(`${s.label.padEnd(46)} ${String(list.length).padStart(2)} controls`);
    } catch (e) { console.log(`${s.label.padEnd(46)} FAILED ${String(e).split("\n")[0].slice(0, 100)}`); fields.push({ page: s.url, state: s.label, role: s.role, tag: "ERROR", name: String(e).split("\n")[0].slice(0, 120) }); }
    await ctx.close();
  }
  // every admin panel as sysadmin: did it load data or show an error?
  const tok = await tokenFor("sysadmin");
  for (const name of ADMIN_PANELS) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
    await ctx.addInitScript(({ a, r }) => { localStorage.setItem("access_token", a); localStorage.setItem("refresh_token", r); }, tok);
    const page = await ctx.newPage();
    const bad = [];
    page.on("response", (r) => { if (r.status() >= 400 && r.url().includes("/api/")) bad.push(`${r.request().method()} ${r.url().replace(API, "")} ${r.status()}`); });
    page.on("pageerror", (e) => bad.push("pageerror " + String(e).slice(0, 80)));
    await page.goto(WEB + "/admin", { waitUntil: "load" });
    await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
    await page.getByRole("button", { name: name, exact: false }).first().click();
    await page.waitForTimeout(1500);
    const main = await page.locator("main").last().innerText().catch(() => "");
    panels.push({ panel: name, error_banner: /could not|failed|error|unavailable/i.test(main) && !/0 errors/i.test(main), http_errors: bad.join("; "), spinner_left: await page.locator(".animate-spin").count(), text: main.replace(/\s+/g, " ").slice(0, 160) });
    console.log(`panel ${name.padEnd(24)} errors=${bad.length} text="${main.replace(/\s+/g, " ").slice(0, 70)}"`);
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "field_audit.json"), JSON.stringify({ fields, panels }, null, 1));
  const cols = ["page", "state", "role", "tag", "type", "name", "name_source", "id", "testid", "required", "min", "max", "minlength", "maxlength", "pattern", "autocomplete", "placeholder", "initial", "options", "disabled", "readonly", "described_by"];
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  fs.writeFileSync(path.join(OUT, "field_completeness.csv"), [cols.join(","), ...fields.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n"));
  console.log(`\n${fields.length} fields in ${STATES.length} states; ${panels.length} admin panels`);
})().catch((e) => { console.error("FAILED", e); process.exit(1); });
