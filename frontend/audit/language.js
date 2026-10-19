/**
 * Language audit: switches each public page to Tamil and measures what actually changed.
 *
 *   node audit/language.js [outDir]       (env: WEB, API)
 *
 * Reports, per page: share of visible letters that are Tamil in English mode and in Tamil mode, the number of text
 * nodes that changed, the <html lang> value, and whether the choice survives a reload. Tamil text in the data itself
 * (name_ta fields) counts, so a page of schemes is partly Tamil even in English mode by design.
 */
const { chromium } = require("playwright-core");
const fs = require("fs");
const path = require("path");

const WEB = process.env.WEB || "http://localhost:3000";
const API = process.env.API || "http://localhost:8000";
const OUT = process.argv[2] || path.join(__dirname, "out");
fs.mkdirSync(OUT, { recursive: true });

const MEASURE = `(() => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const el = n.parentElement; if (!el) continue;
    const s = getComputedStyle(el); const r = el.getBoundingClientRect();
    if (s.display === "none" || s.visibility === "hidden" || r.width === 0) continue;
    const t = n.textContent.replace(/\\s+/g, " ").trim(); if (t) nodes.push(t);
  }
  const all = nodes.join(" ");
  const tamil = (all.match(/[\\u0B80-\\u0BFF]/g) || []).length;
  const letters = (all.match(/[A-Za-z\\u0B80-\\u0BFF]/g) || []).length;
  return { nodes, tamil_letters: tamil, letters, lang: document.documentElement.lang };
})()`;

(async () => {
  const schemes = await (await fetch(`${API}/api/v1/schemes?page_size=1`)).json();
  const id = schemes.items[0].scheme_id;
  const pages = ["/", "/login", "/register", "/schemes", `/schemes/${id}`, "/services", "/documents", "/complaints", "/assistant"];
  const browser = await chromium.launch();
  const rows = [];
  for (const url of pages) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
    const page = await ctx.newPage();
    await page.goto(WEB + url, { waitUntil: "load" });
    await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
    await page.waitForTimeout(600);
    const en = await page.evaluate(MEASURE);
    await page.getByRole("button", { name: "தமிழ்" }).first().click();
    await page.waitForTimeout(700);
    const ta = await page.evaluate(MEASURE);
    await page.reload({ waitUntil: "load" });
    await page.waitForTimeout(700);
    const again = await page.evaluate(MEASURE);
    const changed = ta.nodes.filter((t) => !en.nodes.includes(t)).length;
    rows.push({
      page: url.replace(id, ":id"), lang_en: en.lang, lang_ta: ta.lang, text_nodes: en.nodes.length,
      tamil_share_en: +(en.tamil_letters / Math.max(1, en.letters) * 100).toFixed(1), tamil_share_ta: +(ta.tamil_letters / Math.max(1, ta.letters) * 100).toFixed(1),
      nodes_changed: changed, persists_after_reload: again.lang === "ta",
    });
    console.log(JSON.stringify(rows[rows.length - 1]));
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "language_audit.json"), JSON.stringify(rows, null, 1));
})().catch((e) => { console.error("FAILED", e); process.exit(1); });
