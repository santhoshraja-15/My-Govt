"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Search, Globe, ArrowLeft, ExternalLink, FileText, Loader2, Calendar, Download, ChevronDown } from "lucide-react";
import { documents as docsAPI } from "@/lib/api";
import { ErrorState } from "@/components/ui/AsyncState";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { useLang, type TKey } from "@/lib/i18n";

// The four visible groups. "orders" combines Government Orders with departmental policy documents.
const GROUPS = [
  { key: "all", cats: "", label: "common.all" },
  { key: "orders", cats: "government_order,policy", label: "docs.group.orders" },
  { key: "circular", cats: "circular", label: "cat.circular" },
  { key: "notification", cats: "notification", label: "cat.notification" },
  { key: "act", cats: "act", label: "cat.act" },
] as const;

function DocCard({ doc }: { doc: any }) {
  const { t, label, pickL, fmtDate } = useLang();
  const [open, setOpen] = useState(false);
  const summary = pickL(doc.summary_en, doc.summary_ta);
  const showTamilNote = summary.lang === "ta" && !doc.summary_ta_reviewed;
  const topics: string[] = doc.related_topics ?? [];
  return (
    <article className="card p-5 flex flex-col gap-3" data-testid="policy-doc" data-code={doc.doc_code} data-category={doc.category}>
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0"><FileText size={18} className="text-indigo-600" aria-hidden /></div>
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-slate-900 text-sm mb-1 [overflow-wrap:anywhere]" lang="en">{doc.title}</h3>
          {doc.title_ta && <p className="text-xs text-slate-600 mb-1" lang="ta"><span className="sr-only">{t("docs.officialTitleTa")}: </span>{doc.title_ta}</p>}
          <div className="flex flex-wrap gap-2 mb-2">
            <span className="badge badge-blue">{label("cat", doc.category)}</span>
            <span className="badge badge-slate max-w-full truncate" title={doc.issuing_authority} lang="en">{doc.issuing_authority}</span>
            <span className="badge badge-purple">{t(`docs.lang.${doc.language}` as TKey)}</span>
            <VerificationBadge status={doc.verification_status} />
          </div>
          <dl className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-600">
            {doc.identifier && <div className="flex gap-1"><dt className="text-slate-500">{t("docs.identifier")}:</dt><dd className="font-mono [overflow-wrap:anywhere]" lang="en">{doc.identifier}</dd></div>}
            <div className="flex items-center gap-1"><Calendar size={11} aria-hidden /><dt className="text-slate-500">{t("docs.issued")}:</dt>
              <dd data-testid="doc-date" data-iso={doc.issued_on ?? ""}>{doc.issued_on ? fmtDate(doc.issued_on) : t("docs.dateUnconfirmed")}</dd></div>
          </dl>
        </div>
      </div>

      <p className="text-sm text-slate-700 leading-relaxed" lang={summary.lang}>{summary.text}</p>
      {showTamilNote && <p className="text-xs text-slate-500">{t("docs.tamilSummaryNote")}</p>}
      {topics.length > 0 && <p className="text-xs text-slate-600"><b>{t("docs.relatedTo")}:</b> <span lang="en">{topics.join(", ")}</span></p>}

      <div className="flex flex-wrap items-center gap-3 pt-1">
        {doc.pdf_url ? (
          <a href={doc.pdf_url} target="_blank" rel="noopener noreferrer" className="btn-primary text-sm" data-testid="doc-pdf" title={t("common.leavingNotice")}>
            <Download size={14} aria-hidden /> {t("docs.downloadPdf")}<span className="sr-only"> {t("common.opensExternal")}</span>
          </a>
        ) : (
          <a href={doc.source_page_url} target="_blank" rel="noopener noreferrer" className="btn-secondary text-sm" data-testid="doc-landing" title={t("common.leavingNotice")}>
            <ExternalLink size={14} aria-hidden /> {t("docs.viewOfficial")}<span className="sr-only"> {t("common.opensExternal")}</span>
          </a>
        )}
        <a href={doc.source_page_url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-700 underline" title={t("common.leavingNotice")}>
          {t("docs.officialListing")}<span className="sr-only"> {t("common.opensExternal")}</span>
        </a>
        {doc.pdf_pages ? <span className="text-xs text-slate-500">{t("docs.pdfPages", { n: doc.pdf_pages })}</span> : null}
        <button type="button" className="ml-auto text-xs text-slate-600 inline-flex items-center gap-1 hover:text-slate-900" aria-expanded={open} onClick={() => setOpen((o) => !o)} data-testid="doc-details-toggle">
          {open ? t("docs.hideDetails") : t("docs.details")} <ChevronDown size={14} className={open ? "rotate-180" : ""} aria-hidden />
        </button>
      </div>

      {open && (
        <dl className="text-xs text-slate-700 space-y-1.5 border-t border-slate-100 pt-3" data-testid="doc-details">
          {doc.legal_status && <div><dt className="inline font-semibold">{t("docs.legalStatus")}: </dt><dd className="inline" lang="en">{doc.legal_status}</dd></div>}
          {doc.verification_method && <div><dt className="inline font-semibold">{t("docs.method")}: </dt><dd className="inline" lang="en">{doc.verification_method}</dd></div>}
          {doc.last_checked_on && <div>{t("docs.lastChecked", { date: fmtDate(doc.last_checked_on) })}</div>}
          {doc.verification_status === "official_verified" && <div className="text-emerald-700">{t("docs.verifiedNote")}</div>}
          {doc.notes && <div><dt className="inline font-semibold">{t("docs.notesLabel")}: </dt><dd className="inline" lang="en">{doc.notes}</dd></div>}
          <div className="text-slate-500">{t("docs.docLanguage", { lang: t(`docs.lang.${doc.language}` as TKey) })}</div>
        </dl>
      )}
    </article>
  );
}

export default function DocumentsPage() {
  const { t, label } = useLang();
  const [items, setItems] = useState<any[]>([]);
  const [facets, setFacets] = useState<any>({ categories: {}, authorities: [], years: [] });
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [q, setQ] = useState("");
  const [inputVal, setInputVal] = useState("");
  const [group, setGroup] = useState<(typeof GROUPS)[number]["key"]>("all");
  const [authority, setAuthority] = useState("");
  const [year, setYear] = useState("");
  const [language, setLanguage] = useState("");
  const [verification, setVerification] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);

  useEffect(() => {
    const g = new URLSearchParams(window.location.search).get("group");
    if (g && GROUPS.some((x) => x.key === g)) setGroup(g as any);
  }, []);

  const load = useCallback(async (pg = 1) => {
    setLoading(true); setError(false);
    try {
      const cats = GROUPS.find((g) => g.key === group)?.cats;
      const res = await docsAPI.policy({ q: q || undefined, category: cats || undefined, authority, year, language, verification_status: verification, sort, page: pg, page_size: 10 });
      setItems(res.items || []); setTotal(res.total || 0); setPages(res.pages || 1); setPage(pg); setFacets(res.facets || { categories: {}, authorities: [], years: [] });
    } catch { setItems([]); setTotal(0); setError(true); }
    setLoading(false);
  }, [q, group, authority, year, language, verification, sort]);
  useEffect(() => { load(1); }, [load]);

  const counts = facets.categories || {};
  const countFor = (key: string) => {
    if (key === "all") return Object.values(counts).reduce((a: number, b: any) => a + b, 0) as number;
    if (key === "orders") return (counts.government_order ?? 0) + (counts.policy ?? 0);
    return counts[key] ?? 0;
  };
  const filtered = !!(q || authority || year || language || verification);
  const clearAll = () => { setQ(""); setInputVal(""); setAuthority(""); setYear(""); setLanguage(""); setVerification(""); setGroup("all"); setSort("newest"); };

  // With the "All" tab the page is split into the four groups so the categories stay visibly separate.
  const sections = useMemo(() => {
    if (group !== "all") return [{ key: group as string, items }];
    const order: [string, string[]][] = [["orders", ["government_order", "policy"]], ["circular", ["circular"]], ["notification", ["notification"]], ["act", ["act"]]];
    return order.map(([key, cats]) => ({ key, items: items.filter((d) => cats.includes(d.category)) })).filter((s) => s.items.length);
  }, [items, group]);

  const groupLabel = (k: string) => (k === "orders" ? t("docs.group.orders") : label("cat", k));

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-indigo-800 to-indigo-600 text-white py-12">
        <div className="max-w-5xl mx-auto px-4">
          <Link href="/" className="inline-flex items-center gap-1.5 text-indigo-200 hover:text-white text-sm mb-4"><ArrowLeft size={16} /> {t("common.home")}</Link>
          <div className="flex items-center gap-3 mb-2">
            <Globe size={30} className="text-indigo-300" aria-hidden />
            <h1 className="text-3xl font-black">{t("docs.title")}</h1>
          </div>
          <p className="text-indigo-100 mb-6 max-w-3xl">{t("docs.subtitle")}</p>
          <form onSubmit={(e) => { e.preventDefault(); setQ(inputVal.trim()); }} role="search" className="flex flex-wrap gap-2 max-w-2xl">
            <div className="flex-1 min-w-[12rem] flex items-center gap-2 bg-white/15 border border-white/20 rounded-xl px-4 py-2.5">
              <Search size={18} className="text-indigo-200 shrink-0" aria-hidden />
              <input value={inputVal} onChange={(e) => setInputVal(e.target.value)} aria-label={t("docs.searchLabel")} data-testid="document-search"
                placeholder={t("docs.searchPlaceholder")} className="flex-1 min-w-0 bg-transparent text-white placeholder-indigo-300 text-sm outline-none" />
            </div>
            <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600">{t("common.search")}</button>
          </form>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div role="tablist" aria-label={t("docs.categoryNav")} className="flex flex-wrap gap-2 mb-5">
          {GROUPS.map((g) => (
            <button key={g.key} role="tab" aria-selected={group === g.key} data-testid={`doc-group-${g.key}`} onClick={() => setGroup(g.key)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-all ${group === g.key ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200 hover:border-brand-300"}`}>
              {t(g.label as TKey)} <span className="opacity-80">({countFor(g.key)})</span>
            </button>
          ))}
        </div>

        <div className="card p-4 mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5" data-testid="doc-filters">
          <div><label htmlFor="f-dept" className="label text-xs">{t("docs.department")}</label>
            <select id="f-dept" className="input text-xs" value={authority} onChange={(e) => setAuthority(e.target.value)} data-testid="filter-authority">
              <option value="">{t("docs.allDepartments")}</option>{(facets.authorities || []).map((a: string) => <option key={a} value={a}>{a}</option>)}</select></div>
          <div><label htmlFor="f-year" className="label text-xs">{t("docs.year")}</label>
            <select id="f-year" className="input text-xs" value={year} onChange={(e) => setYear(e.target.value)} data-testid="filter-year">
              <option value="">{t("docs.allYears")}</option>{(facets.years || []).map((y: number) => <option key={y} value={y}>{y}</option>)}</select></div>
          <div><label htmlFor="f-lang" className="label text-xs">{t("docs.language")}</label>
            <select id="f-lang" className="input text-xs" value={language} onChange={(e) => setLanguage(e.target.value)} data-testid="filter-language">
              <option value="">{t("docs.allLanguages")}</option><option value="en">{t("docs.lang.en")}</option><option value="ta">{t("docs.lang.ta")}</option><option value="bilingual">{t("docs.lang.bilingual")}</option></select></div>
          <div><label htmlFor="f-ver" className="label text-xs">{t("docs.verification")}</label>
            <select id="f-ver" className="input text-xs" value={verification} onChange={(e) => setVerification(e.target.value)} data-testid="filter-verification">
              <option value="">{t("docs.allVerification")}</option><option value="official_verified">{t("status.verified")}</option><option value="provisional">{t("status.provisional")}</option></select></div>
          <div><label htmlFor="f-sort" className="label text-xs">{t("docs.sort")}</label>
            <select id="f-sort" className="input text-xs" value={sort} onChange={(e) => setSort(e.target.value)} data-testid="doc-sort">
              <option value="newest">{t("docs.sort.newest")}</option><option value="oldest">{t("docs.sort.oldest")}</option><option value="title">{t("docs.sort.title")}</option></select></div>
        </div>

        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-slate-500" data-testid="doc-count" aria-live="polite">{loading ? t("common.loading") : error ? "" : total === 1 ? t("docs.countOne") : t("docs.count", { count: total })}</p>
          {(filtered || group !== "all") && <button type="button" className="text-xs text-brand-700 underline" onClick={clearAll} data-testid="doc-clear">{t("docs.clearAll")}</button>}
        </div>

        {loading ? (
          <div className="flex justify-center py-20" role="status" aria-label={t("common.loading")}><Loader2 size={32} className="animate-spin text-brand-600" /></div>
        ) : error ? (
          <ErrorState message={t("docs.loadFailed")} onRetry={() => load(1)} />
        ) : items.length === 0 ? (
          <div className="text-center py-20" data-testid="empty-state">
            <FileText size={48} className="text-slate-300 mx-auto mb-3" aria-hidden />
            <p className="text-slate-600 font-medium">{t("docs.empty")}</p>
            <p className="text-sm text-slate-500">{t("docs.emptyHint")}</p>
          </div>
        ) : (
          <div className="space-y-8">
            {sections.map((s) => (
              <section key={s.key} aria-labelledby={`grp-${s.key}`} data-testid={`doc-section-${s.key}`}>
                {group === "all" && <h2 id={`grp-${s.key}`} className="font-bold text-slate-900 mb-3">{groupLabel(s.key)}</h2>}
                <div className="space-y-3">{s.items.map((d: any) => <DocCard key={d.doc_code} doc={d} />)}</div>
              </section>
            ))}
          </div>
        )}

        {pages > 1 && !loading && (
          <nav className="flex justify-center items-center gap-2 mt-10" aria-label={t("common.page", { page, pages })}>
            <button onClick={() => load(page - 1)} disabled={page === 1} className="btn-ghost disabled:opacity-40">{t("pager.prev")}</button>
            <span className="text-sm text-slate-600">{t("common.page", { page, pages })}</span>
            <button onClick={() => load(page + 1)} disabled={page === pages} className="btn-ghost disabled:opacity-40">{t("pager.next")}</button>
          </nav>
        )}
      </div>
    </div>
  );
}
