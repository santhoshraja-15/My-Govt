"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { Search, Globe, ArrowLeft, ExternalLink, FileText, Loader2, Calendar } from "lucide-react";
import { documents as docsAPI } from "@/lib/api";

const DOC_TYPES = ["All", "government_order", "policy", "act", "circular", "notification", "report"];

export default function DocumentsPage() {
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [inputVal, setInputVal] = useState("");
  const [docType, setDocType] = useState("All");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);

  const load = useCallback(async (pg = 1) => {
    setLoading(true);
    try {
      const res = await docsAPI.list({
        q: q || undefined,
        doc_type: docType === "All" ? undefined : docType,
        page: pg, page_size: 15,
      });
      setItems(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
      setPage(pg);
    } catch { setItems([]); }
    setLoading(false);
  }, [q, docType]);

  useEffect(() => { load(1); }, [load]);

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-indigo-800 to-indigo-600 text-white py-12">
        <div className="max-w-5xl mx-auto px-4">
          <Link href="/" className="inline-flex items-center gap-1.5 text-indigo-200 hover:text-white text-sm mb-4">
            <ArrowLeft size={16} /> Home
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <Globe size={30} className="text-indigo-300" />
            <h1 className="text-3xl font-black">Policy Documents</h1>
          </div>
          <p className="text-indigo-200 mb-6">Government Orders, Acts, Policies and Official Circulars</p>
          <form onSubmit={e => { e.preventDefault(); setQ(inputVal); }} role="search" className="flex flex-wrap gap-2 max-w-xl">
            <div className="flex-1 min-w-[12rem] flex items-center gap-2 bg-white/15 border border-white/20 rounded-xl px-4 py-2.5">
              <Search size={18} className="text-indigo-200 shrink-0" />
              <input value={inputVal} onChange={e => setInputVal(e.target.value)} aria-label="Search documents" data-testid="document-search"
                placeholder="Search documents…" className="flex-1 min-w-0 bg-transparent text-white placeholder-indigo-300 text-sm outline-none" />
            </div>
            <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600">Search</button>
          </form>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8">
        <div className="flex flex-wrap gap-2 mb-6">
          {DOC_TYPES.map(t => (
            <button key={t} onClick={() => setDocType(t)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium border transition-all ${
                docType === t ? "bg-brand-600 text-white border-brand-600" : "bg-white text-slate-600 border-slate-200 hover:border-brand-300"}`}>
              {t === "All" ? "All Types" : t.replace(/_/g, " ")}
            </button>
          ))}
        </div>

        <p className="text-sm text-slate-500 mb-5">{loading ? "Loading…" : `${total} document${total !== 1 ? "s" : ""}`}</p>

        {loading ? (
          <div className="flex justify-center py-20"><Loader2 size={32} className="animate-spin text-brand-600" /></div>
        ) : items.length === 0 ? (
          <div className="text-center py-20">
            <FileText size={48} className="text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">No documents found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {items.map((doc: any) => (
              <div key={doc.document_id} className="card p-5 flex items-start gap-4 hover:border-brand-200 transition-all">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center shrink-0">
                  <FileText size={18} className="text-indigo-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-slate-900 text-sm mb-1 line-clamp-2">{doc.title}</h3>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {doc.doc_type && <span className="badge badge-blue capitalize">{doc.doc_type.replace(/_/g," ")}</span>}
                    {doc.department_name && <span className="badge badge-slate">{doc.department_name}</span>}
                    {doc.language && <span className="badge badge-purple uppercase">{doc.language}</span>}
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    {doc.publication_date && (
                      <span className="flex items-center gap-1">
                        <Calendar size={11} />
                        {new Date(doc.publication_date).toLocaleDateString("en-IN")}
                      </span>
                    )}
                  </div>
                </div>
                {doc.source_url && (
                  <a href={doc.source_url} target="_blank" rel="noopener noreferrer"
                    className="btn-ghost text-xs shrink-0 flex items-center gap-1">
                    View <ExternalLink size={12} />
                  </a>
                )}
              </div>
            ))}
          </div>
        )}

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
      </div>
    </div>
  );
}
