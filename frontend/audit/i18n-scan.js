/** Shared by audit/localization.js (demo stack) and e2e/localization.spec.ts (disposable CI stack). */
const ALLOW = "React Flow attribution|React Flow|tsvector|pgcrypto|postgis|vector|btree_gist|pg_trgm|TABLE|NO ACTION|CASCADE|RESTRICT|SET NULL|ON DELETE|CHECK|SELECT|plpgsql|MyGovt|MG|AI|PDF|SQL|GO|G\\.O\\.|UQ|PK|FK|NN|1NF|2NF|3NF|PostgreSQL|PostGIS|pgvector|Neo4j|Redis|MinIO|DML|SLA|BPL|OC|BC|MBC|SC|ST|EN|UMIS|UDID|IP|RCH|PICME|ID|API|ER|DB|JSON|UI|NOT NULL|WITH|CMCHIS|PM-KISAN|KB|ms|h|e-Sevai|DEMO|MYG|DEMO-\\d+|SYN-[\\w-]+|http|https|www";

const SCAN = (args) => {
  const { lang, allow } = args;
  const allowRe = new RegExp(String.raw`\b(?:` + allow + String.raw`)\b`, "gi");
  const latin = /[A-Za-z]{2,}/;
  const tamil = /[஀-௿]/;
  const skipTags = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "NOSCRIPT", "SVG", "PATH", "TEXTAREA"]);
  const bad = [];
  const seen = new Set();
  const okNode = (el) => {
    for (let n = el; n && n.nodeType === 1; n = n.parentElement) {
      if (skipTags.has(n.tagName.toUpperCase())) return true;
      if (lang === "ta" && n.getAttribute("lang") === "en") return true;
      if (lang === "en" && n.getAttribute("lang") === "ta") return true;
      if (n.hasAttribute("data-i18n-skip")) return true;
      if (n.classList && n.classList.contains("font-mono")) return true;   // monospace text is an identifier, SQL or code: never translated
      const tid = n.getAttribute("data-testid") || "";
      if (/secondary-name/.test(tid)) return true;   // bilingual scheme/service names: the other-language name is intentional
    }
    return false;
  };
  const visible = (el) => { const s = getComputedStyle(el); const r = el.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && (r.width > 0 || r.height > 0); };
  const test = (text, where) => {
    const t = text.replace(/\s+/g, " ").trim();
    if (!t) return;
    const key = where + "|" + t;
    if (seen.has(key)) return;
    seen.add(key);
    if (lang === "ta") {
      const stripped = t.replace(/https?:\/\/\S+/g, "").replace(allowRe, " ").replace(/\b[A-Za-z]{1,2}\d*\b/g, " ").replace(/[A-Za-z]+[-_.:/][A-Za-z0-9_.:/-]+/g, " ");
      if (latin.test(stripped)) bad.push({ where, text: t.slice(0, 140) });
    } else if (tamil.test(t)) bad.push({ where, text: t.slice(0, 140) });
  };
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const el = n.parentElement;
    if (!el || okNode(el) || !visible(el)) continue;
    test(n.textContent || "", "text:" + el.tagName.toLowerCase());
  }
  for (const el of document.querySelectorAll("[placeholder], [aria-label], [title], img[alt]")) {
    if (okNode(el)) continue;
    for (const a of ["placeholder", "aria-label", "title", "alt"]) { const v = el.getAttribute(a); if (v) test(v, "attr:" + a); }
  }
  for (const el of document.querySelectorAll("option")) { if (!okNode(el)) test(el.textContent || "", "option"); }
  return bad;
};

module.exports = { ALLOW, SCAN };
