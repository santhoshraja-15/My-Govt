"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Search, Filter, ChevronRight, Award, CheckCircle2, XCircle, AlertCircle, ArrowLeft, X, Loader2, SlidersHorizontal } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";
import { ErrorState } from "@/components/ui/AsyncState";
import { VerificationBadge } from "@/components/ui/VerificationBadge";

const CATEGORIES = [
  "All","education","health_insurance","social_security","agriculture","women_welfare",
  "housing","transport","labour_welfare","fisheries","rural_development","youth_employment",
];

const LEVELS = ["All","state","central","district"];

function SchemeCard({ scheme }: { scheme: any }) {
  return (
    <Link data-testid="scheme-card" href={`/schemes/${scheme.scheme_id}`}
      className="group card p-5 flex flex-col gap-3 hover:border-brand-200">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-bold text-slate-900 text-sm group-hover:text-brand-700 transition-colors line-clamp-2 leading-snug">
            {scheme.name}
          </h3>
          {scheme.name_ta && (
            <p className="text-xs text-slate-400 font-tamil mt-0.5 line-clamp-1">{scheme.name_ta}</p>
          )}
        </div>
        <ChevronRight size={16} className="text-slate-300 group-hover:text-brand-500 group-hover:translate-x-1 transition-all shrink-0 mt-0.5" />
      </div>

      {scheme.description && (
        <p className="text-slate-500 text-xs leading-relaxed line-clamp-2">{scheme.description}</p>
      )}

      <div className="flex flex-wrap gap-2 pt-1">
        {scheme.department_name && (
          <span className="badge badge-blue">{scheme.department_name}</span>
        )}
        {scheme.category && (
          <span className="badge badge-slate">{scheme.category.replace(/_/g," ")}</span>
        )}
        {scheme.scheme_level && (
          <span className="badge badge-green capitalize">{scheme.scheme_level}</span>
        )}
        <VerificationBadge status={scheme.verification_status} />
      </div>
    </Link>
  );
}

function EligibilityModal({ scheme, onClose }: { scheme: any; onClose: () => void }) {
  const [profile, setProfile] = useState<Record<string, any>>({});
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fields = [
    { key: "age", label: "Age (years)", type: "number" },
    { key: "gender", label: "Gender", type: "select", opts: ["", "male", "female", "other"] },
    { key: "annual_income", label: "Annual Income (₹)", type: "number" },
    { key: "social_category", label: "Social Category", type: "select", opts: ["", "SC", "ST", "OBC", "MBC", "OC"] },
    { key: "bpl_status", label: "BPL Family?", type: "select", opts: ["", "true", "false"] },
    { key: "disability_status", label: "Person with Disability?", type: "select", opts: ["", "true", "false"] },
    { key: "is_student", label: "Currently a Student?", type: "select", opts: ["", "true", "false"] },
    { key: "occupation", label: "Occupation", type: "text" },
    { key: "education_level", label: "Education Level", type: "select", opts: ["", "below_10th", "10th", "12th", "graduate", "postgraduate"] },
  ];

  const check = async () => {
    setLoading(true);
    try {
      const payload: Record<string, any> = {};
      for (const [k, v] of Object.entries(profile)) {
        if (v === "" || v === undefined) continue;
        if (v === "true") payload[k] = true;
        else if (v === "false") payload[k] = false;
        else if (!isNaN(Number(v)) && v !== "") payload[k] = Number(v);
        else payload[k] = v;
      }
      const res = await schemesAPI.checkEligibility(scheme.scheme_id, payload);
      setResult(res);
    } catch { setResult({ overall: "ERROR" }); }
    setLoading(false);
  };

  const overallColor = result?.overall === "ELIGIBLE" ? "emerald" : result?.overall === "NOT_ELIGIBLE" ? "red" : "amber";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b border-slate-100 px-6 py-4 flex items-center justify-between rounded-t-2xl">
          <h2 className="font-bold text-slate-900">Eligibility Check</h2>
          <button onClick={onClose} className="btn-ghost p-2"><X size={18} /></button>
        </div>

        <div className="p-6">
          <p className="text-sm text-slate-600 mb-5 font-medium">
            {scheme.name}
          </p>

          {!result ? (
            <>
              <div className="grid grid-cols-1 gap-4 mb-6">
                {fields.map(({ key, label, type, opts }) => (
                  <div key={key}>
                    <label className="label">{label}</label>
                    {type === "select" ? (
                      <select className="input" value={profile[key] || ""} onChange={e => setProfile(p => ({...p, [key]: e.target.value}))}>
                        {opts?.map(o => <option key={o} value={o}>{o || "— not specified —"}</option>)}
                      </select>
                    ) : (
                      <input type={type} className="input" placeholder="Enter value"
                        value={profile[key] || ""}
                        onChange={e => setProfile(p => ({...p, [key]: e.target.value}))} />
                    )}
                  </div>
                ))}
              </div>
              <button onClick={check} disabled={loading} className="btn-primary w-full justify-center">
                {loading ? <><Loader2 size={16} className="animate-spin" /> Checking…</> : "Check Eligibility"}
              </button>
            </>
          ) : (
            <div className="space-y-4">
              <div className={`rounded-2xl p-5 text-center bg-${overallColor}-50 border-2 border-${overallColor}-200`}>
                {result.overall === "ELIGIBLE" ? <CheckCircle2 size={36} className="text-emerald-500 mx-auto mb-2" /> :
                 result.overall === "NOT_ELIGIBLE" ? <XCircle size={36} className="text-red-500 mx-auto mb-2" /> :
                 <AlertCircle size={36} className="text-amber-500 mx-auto mb-2" />}
                <h3 className={`font-bold text-lg text-${overallColor}-700`}>
                  {result.overall === "ELIGIBLE" ? "You appear eligible" :
                   result.overall === "NOT_ELIGIBLE" ? "Not eligible based on inputs" :
                   "Insufficient data to determine"}
                </h3>
                <p className="text-xs text-slate-500 mt-1">{result.disclaimer}</p>
              </div>

              {result.failing_rules?.length > 0 && (
                <div className="bg-red-50 rounded-xl p-4">
                  <p className="text-sm font-semibold text-red-700 mb-2">Failing criteria:</p>
                  {result.failing_rules.map((r: string, i: number) => (
                    <p key={i} className="text-xs text-red-600 flex items-start gap-1.5 mb-1">
                      <XCircle size={12} className="mt-0.5 shrink-0" /> {r}
                    </p>
                  ))}
                </div>
              )}

              {result.missing_attributes?.length > 0 && (
                <div className="bg-amber-50 rounded-xl p-4">
                  <p className="text-sm font-semibold text-amber-700 mb-1">Additional info needed:</p>
                  <p className="text-xs text-amber-600">{result.missing_attributes.join(", ")}</p>
                </div>
              )}

              <button onClick={() => setResult(null)} className="btn-secondary w-full justify-center">
                Re-check with different values
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function SchemesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("All");
  const [level, setLevel] = useState("All");
  const [showFilters, setShowFilters] = useState(false);
  const [eligScheme, setEligScheme] = useState<any>(null);
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
    } catch (e: any) { setItems([]); setTotal(0); setError(e?.message || "Could not load schemes."); }
    setLoading(false);
  }, [q, category, level]);

  useEffect(() => { load(1); }, [load]);

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
            <ArrowLeft size={16} /> Back to Home
          </Link>
          <div className="flex items-center gap-3 mb-3">
            <Award size={32} className="text-saffron-400" />
            <h1 className="text-3xl font-black">Government Schemes</h1>
          </div>
          <p className="text-blue-200 text-lg">Discover {total > 0 ? total : ""} Tamil Nadu government benefit programmes</p>

          {/* Search */}
          <form onSubmit={handleSearch} className="mt-6 flex gap-2 max-w-xl">
            <div className="flex-1 flex items-center gap-2 bg-white/15 backdrop-blur border border-white/20 rounded-xl px-4 py-2.5">
              <Search size={18} className="text-blue-200 shrink-0" />
              <input value={inputVal} onChange={e => setInputVal(e.target.value)}
                placeholder="Search schemes…" className="flex-1 bg-transparent text-white placeholder-blue-300 text-sm outline-none" />
            </div>
            <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shrink-0">Search</button>
            <button type="button" onClick={() => setShowFilters(s => !s)} aria-label="Toggle filters" aria-expanded={showFilters}
              className="btn-ghost bg-white/10 hover:bg-white/20 text-white border border-white/20 rounded-xl">
              <SlidersHorizontal size={18} />
            </button>
          </form>

          {/* Filters */}
          {showFilters && (
            <div className="mt-3 flex flex-wrap gap-3 animate-slide-up">
              <div>
                <label className="text-xs text-blue-300 mb-1 block">Category</label>
                <select className="input bg-white/15 border-white/20 text-white text-xs py-1.5"
                  value={category} onChange={e => setCategory(e.target.value)}>
                  {CATEGORIES.map(c => <option key={c} value={c} className="text-slate-900">{c === "All" ? "All Categories" : c.replace(/_/g," ")}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs text-blue-300 mb-1 block">Level</label>
                <select className="input bg-white/15 border-white/20 text-white text-xs py-1.5"
                  value={level} onChange={e => setLevel(e.target.value)}>
                  {LEVELS.map(l => <option key={l} value={l} className="text-slate-900">{l === "All" ? "All Levels" : l}</option>)}
                </select>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <p className="text-sm text-slate-500">
            {loading ? "Loading…" : error ? "" : `${total} scheme${total !== 1 ? "s" : ""} found`}
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
            <h3 className="font-semibold text-slate-600 mb-1">No schemes found</h3>
            <p className="text-sm text-slate-400">Try different keywords or remove filters</p>
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
                  className="btn-ghost disabled:opacity-40">← Prev</button>
                {Array.from({length: Math.min(pages, 7)}, (_, i) => i + 1).map(p => (
                  <button key={p} onClick={() => load(p)}
                    className={`w-9 h-9 rounded-xl text-sm font-semibold transition-all ${p === page ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                    {p}
                  </button>
                ))}
                <button onClick={() => load(page + 1)} disabled={page === pages}
                  className="btn-ghost disabled:opacity-40">Next →</button>
              </div>
            )}
          </>
        )}
      </div>

      {eligScheme && <EligibilityModal scheme={eligScheme} onClose={() => setEligScheme(null)} />}
    </div>
  );
}
