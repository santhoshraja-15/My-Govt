"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Search, Filter, ChevronRight, Award, ArrowLeft, SlidersHorizontal } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";
import { ErrorState } from "@/components/ui/AsyncState";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { useLang } from "@/lib/i18n";

const LEVELS = ["All","state","central","district"];

function SchemeCard({ scheme }: { scheme: any }) {
  const { names, pickL, label, dept } = useLang();
  const desc = pickL(scheme.description, scheme.description_ta);
  const nm = names(scheme.name, scheme.name_ta);
  return (
    <Link data-testid="scheme-card" href={`/schemes/${scheme.scheme_id}`}
      className="group card p-5 flex flex-col gap-3 hover:border-brand-200">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-slate-900 text-sm group-hover:text-brand-700 transition-colors line-clamp-2 leading-snug">
            {nm.primary}
          </h3>
          {nm.secondary && (
            <p className="text-xs text-slate-500 mt-0.5 line-clamp-1" data-testid="scheme-secondary-name" data-i18n-skip lang={nm.secondaryLang}>{nm.secondary}</p>
          )}
        </div>
        <ChevronRight size={16} className="text-slate-300 group-hover:text-brand-500 group-hover:translate-x-1 transition-all shrink-0 mt-0.5" />
      </div>

      {scheme.description && (
        <p className="text-slate-500 text-xs leading-relaxed line-clamp-2" lang={desc.lang}>{desc.text}</p>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {scheme.department_name && (
          <span className="badge badge-blue max-w-full truncate" title={dept(scheme.department_name)}>{dept(scheme.department_name)}</span>
        )}
        {scheme.category && (
          <span className="badge badge-slate">{label("cat", scheme.category)}</span>
        )}
        {scheme.scheme_level && (
          <span className="badge badge-green capitalize">{label("level", scheme.scheme_level)}</span>
        )}
        <VerificationBadge status={scheme.verification_status} />
      </div>
    </Link>
  );
}

export default function SchemesPage() {
  const { t, label } = useLang();
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("All");
  const [level, setLevel] = useState("All");
  const [showFilters, setShowFilters] = useState(false);
  const [cats, setCats] = useState<string[]>([]);
  const [inputVal, setInputVal] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async (pg = 1) => {
    setLoading(true);
    setError("");
    try {
      const res = await schemesAPI.list({
        q: q || undefined,
        category: category === "All" ? undefined : category,
        level: level === "All" ? undefined : level,
        page: pg, page_size: 12,
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
      setPage(pg);
    } catch (e: any) { setItems([]); setTotal(0); setError(t("schemes.loadFailed")); }
    setLoading(false);
  }, [q, category, level]);

  useEffect(() => { load(1); }, [load]);
  useEffect(() => { schemesAPI.categories().then(setCats).catch(() => setCats([])); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setQ(inputVal);
  };

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-brand-800 to-brand-600 text-white py-12">
        <div className="max-w-6xl mx-auto px-4">
          <Link href="/" className="inline-flex items-center gap-1.5 text-blue-200 hover:text-white text-sm mb-4 transition-colors">
            <ArrowLeft size={16} /> {t("schemes.back")}
          </Link>
          <div className="flex items-center gap-3 mb-3">
            <Award size={32} className="text-saffron-400" />
            <h1 className="text-3xl font-black">{t("schemes.title")}</h1>
          </div>
          <p className="text-blue-200 text-lg">{total > 0 ? t("schemes.subtitle", { count: total }) : t("schemes.subtitleNoCount")}</p>

          {/* Search */}
          <form onSubmit={handleSearch} role="search" className="mt-6 flex flex-wrap gap-2 max-w-xl">
            <div className="flex-1 min-w-[12rem] flex items-center gap-2 bg-white/15 backdrop-blur border border-white/20 rounded-xl px-4 py-2.5">
              <Search size={18} className="text-blue-200 shrink-0" />
              <input value={inputVal} onChange={e => setInputVal(e.target.value)} aria-label={t("schemes.searchLabel")} data-testid="scheme-search"
                placeholder={t("schemes.searchPlaceholder")} className="flex-1 min-w-0 bg-transparent text-white placeholder-blue-300 text-sm outline-none" />
            </div>
            <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shrink-0">{t("common.search")}</button>
            <button type="button" onClick={() => setShowFilters(s => !s)} aria-label={t("schemes.toggleFilters")} aria-expanded={showFilters}
              className="btn-ghost bg-white/10 hover:bg-white/20 text-white border border-white/20 rounded-xl">
              <SlidersHorizontal size={18} />
            </button>
          </form>

          {/* Filters */}
          {showFilters && (
            <div className="mt-3 flex flex-wrap gap-3 animate-slide-up">
              <div>
                <label htmlFor="scheme-category" className="text-xs text-blue-100 mb-1 block">{t("schemes.category")}</label>
                <select id="scheme-category" className="input bg-white/15 border-white/20 text-white text-xs py-1.5"
                  value={category} onChange={e => setCategory(e.target.value)}>
                  {["All", ...cats].map(c => <option key={c} value={c} className="text-slate-900">{c === "All" ? t("schemes.allCategories") : label("cat", c)}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="scheme-level" className="text-xs text-blue-100 mb-1 block">{t("schemes.level")}</label>
                <select id="scheme-level" className="input bg-white/15 border-white/20 text-white text-xs py-1.5"
                  value={level} onChange={e => setLevel(e.target.value)}>
                  {LEVELS.map(l => <option key={l} value={l} className="text-slate-900">{l === "All" ? t("schemes.allLevels") : label("level", l)}</option>)}
                </select>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <h2 className="sr-only">{t("schemes.resultsHeading")}</h2>
        <div className="flex items-center justify-between mb-6">
          <p className="text-sm text-slate-500">
            {loading ? t("common.loading") : error ? "" : total === 1 ? t("schemes.foundOne") : t("schemes.found", { count: total })}
          </p>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {Array.from({length: 9}).map((_, i) => (
              <div key={i} className="card p-5 flex flex-col gap-3">
                <div className="skeleton h-4 w-3/4" />
                <div className="skeleton h-3 w-full" />
                <div className="skeleton h-3 w-2/3" />
                <div className="flex gap-2"><div className="skeleton h-5 w-16 rounded-full" /><div className="skeleton h-5 w-20 rounded-full" /></div>
              </div>
            ))}
          </div>
        ) : error ? (
          <ErrorState message={error} onRetry={() => load(1)} />
        ) : items.length === 0 ? (
          <div className="text-center py-20" data-testid="empty-state">
            <Award size={48} className="text-slate-300 mx-auto mb-4" />
            <h3 className="font-semibold text-slate-600 mb-1">{t("schemes.emptyTitle")}</h3>
            <p className="text-sm text-slate-500">{t("schemes.emptyText")}</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {items.map(s => <SchemeCard key={s.scheme_id} scheme={s} />)}
            </div>
            {/* Pagination */}
            {pages > 1 && (
              <div className="flex justify-center items-center gap-2 mt-10">
                <button onClick={() => load(page - 1)} disabled={page === 1}
                  className="btn-ghost disabled:opacity-40">{t("pager.prev")}</button>
                {Array.from({length: Math.min(pages, 7)}, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => load(p)}
                    className={`w-9 h-9 rounded-xl text-sm font-semibold transition-all ${p === page ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                    {p}
                  </button>
                ))}
                <button onClick={() => load(page + 1)} disabled={page === pages}
                  className="btn-ghost disabled:opacity-40">{t("pager.next")}</button>
              </div>
            )}
          </>
        )}
      </div>

    </div>
  );
}
