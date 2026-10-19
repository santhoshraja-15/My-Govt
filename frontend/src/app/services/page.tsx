"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { Search, FileText, ArrowLeft, ExternalLink, Download, Loader2, Filter } from "lucide-react";
import { services as servicesAPI } from "@/lib/api";
import { ErrorState } from "@/components/ui/AsyncState";
import { VerificationBadge } from "@/components/ui/VerificationBadge";

function ServiceCard({ svc }: { svc: any }) {
  return (
    <Link data-testid="service-card" href={`/services/${svc.service_id}`}
      className="group card p-5 flex gap-4 items-start hover:border-brand-200">
      <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
        <FileText size={18} className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <h3 className="font-bold text-slate-900 text-sm group-hover:text-brand-700 transition-colors line-clamp-1 mb-0.5">{svc.name}</h3>
        {svc.name_ta && <p className="text-xs text-slate-500 font-tamil line-clamp-1 mb-2">{svc.name_ta}</p>}
        {svc.description && <p className="text-xs text-slate-500 line-clamp-2 leading-relaxed">{svc.description}</p>}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {svc.department_name && <span className="badge badge-blue max-w-full truncate" title={svc.department_name}>{svc.department_name}</span>}
          {svc.charges_verified ? (
            <>
              {svc.government_fee > 0 && <span className="badge badge-green">₹{svc.government_fee} fee</span>}
              {svc.government_fee === 0 && <span className="badge badge-green">Free</span>}
              {svc.processing_time && <span className="badge badge-slate">{svc.processing_time}</span>}
            </>
          ) : (
            <span className="badge badge-yellow" data-testid="charges-unconfirmed" title="Fees and processing time for this service have not been verified against an official source">
              Fees &amp; timing unconfirmed
            </span>
          )}
          <VerificationBadge status={svc.verification_status} />
        </div>
      </div>
    </Link>
  );
}

export default function ServicesPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [inputVal, setInputVal] = useState("");
  const [category, setCategory] = useState("All");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [cats, setCats] = useState<string[]>([]);

  const load = useCallback(async (pg = 1) => {
    setLoading(true);
    setError("");
    try {
      const res = await servicesAPI.list({
        q: q || undefined,
        category: category === "All" ? undefined : category,
        page: pg, page_size: 12,
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
      setPage(pg);
    } catch (e: any) { setItems([]); setTotal(0); setError(e?.message || "Could not load services."); }
    setLoading(false);
  }, [q, category]);

  useEffect(() => { load(1); }, [load]);
  useEffect(() => { servicesAPI.categories().then(setCats).catch(() => setCats([])); }, []);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-emerald-800 to-teal-700 text-white py-12">
        <div className="max-w-6xl mx-auto px-4">
          <Link href="/" className="inline-flex items-center gap-1.5 text-emerald-200 hover:text-white text-sm mb-4 transition-colors">
            <ArrowLeft size={16} /> Home
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <FileText size={30} className="text-emerald-300" />
            <h1 className="text-3xl font-black">e-Sevai Services</h1>
          </div>
          <p className="text-emerald-200 text-lg mb-6">Apply online for {total > 0 ? total : ""} government certificates and services</p>

          <form onSubmit={(e) => { e.preventDefault(); setQ(inputVal); }} role="search" className="flex flex-wrap gap-2 max-w-xl">
            <div className="flex-1 min-w-[12rem] flex items-center gap-2 bg-white/15 backdrop-blur border border-white/20 rounded-xl px-4 py-2.5">
              <Search size={18} className="text-emerald-200 shrink-0" />
              <input value={inputVal} onChange={e => setInputVal(e.target.value)} aria-label="Search services" data-testid="service-search"
                placeholder="Search services…" className="flex-1 min-w-0 bg-transparent text-white placeholder-emerald-300 text-sm outline-none" />
            </div>
            <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shrink-0">Search</button>
          </form>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Category filter pills */}
        <div className="flex flex-wrap gap-2 mb-6">
          {["All", ...cats].map(c => (
            <button key={c} onClick={() => setCategory(c)} aria-pressed={category === c} data-testid={`service-category-${c}`}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all border ${
                category === c
                  ? "bg-brand-600 text-white border-brand-600 shadow-sm"
                  : "bg-white text-slate-600 border-slate-200 hover:border-brand-300 hover:text-brand-600"}`}>
              {c === "All" ? "All Categories" : c.replace(/_/g," ")}
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between mb-5">
          <p className="text-sm text-slate-500">{loading ? "Loading…" : error ? "" : `${total} service${total !== 1 ? "s" : ""}`}</p>
        </div>

        {loading ? (
          <div className="flex justify-center py-20"><Loader2 size={32} className="animate-spin text-brand-600" /></div>
        ) : error ? (
          <ErrorState message={error} onRetry={() => load(1)} />
        ) : items.length === 0 ? (
          <div className="text-center py-20" data-testid="empty-state">
            <FileText size={48} className="text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">No services found</p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {items.map(s => <ServiceCard key={s.service_id} svc={s} />)}
            </div>
            {pages > 1 && (
              <div className="flex justify-center gap-2 mt-10">
                <button onClick={() => load(page-1)} disabled={page===1} className="btn-ghost disabled:opacity-40">← Prev</button>
                {Array.from({length: Math.min(pages,7)}, (_, i) => i+1).map(p => (
                  <button key={p} onClick={() => load(p)}
                    className={`w-9 h-9 rounded-xl text-sm font-semibold ${p===page ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                    {p}
                  </button>
                ))}
                <button onClick={() => load(page+1)} disabled={page===pages} className="btn-ghost disabled:opacity-40">Next →</button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
