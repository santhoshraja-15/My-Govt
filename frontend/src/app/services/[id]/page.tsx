"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, FileText, Loader2 } from "lucide-react";
import { services as servicesAPI } from "@/lib/api";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { ErrorState } from "@/components/ui/AsyncState";

const money = (n: number) => (n === 0 ? "Free" : `₹${n.toLocaleString("en-IN")}`);

export default function ServiceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [svc, setSvc] = useState<any>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing" | "error">("loading");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setState("loading");
    servicesAPI.get(id).then((s) => { setSvc(s); setState("ok"); })
      .catch((e) => { if (e?.status === 404 || e?.status === 422) setState("missing"); else { setError(e?.message || "Could not load this service."); setState("error"); } });
  }, [id]);
  useEffect(() => { load(); }, [load]);

  if (state === "loading") return <div className="min-h-[60vh] flex items-center justify-center" role="status" aria-label="Loading service"><Loader2 size={32} className="animate-spin text-brand-600" /></div>;
  if (state === "error") return <main className="max-w-3xl mx-auto px-4 py-16"><ErrorState message={error} onRetry={load} /></main>;
  if (state === "missing") {
    return (
      <main className="max-w-3xl mx-auto px-4 py-20 text-center space-y-3" data-testid="service-not-found">
        <FileText size={44} className="text-slate-400 mx-auto" aria-hidden />
        <h1 className="text-xl font-bold text-slate-800">Service not found</h1>
        <p className="text-slate-600">It may have been withdrawn, or the link is wrong.</p>
        <Link href="/services" className="btn-secondary">Back to services</Link>
      </main>
    );
  }

  const reqs: any[] = svc.requirements ?? [];
  const verified = svc.verification_status === "official_verified";
  return (
    <div className="min-h-screen bg-slate-50" data-testid="service-detail">
      <div className="bg-gradient-to-r from-emerald-800 to-teal-700 text-white py-10">
        <div className="max-w-4xl mx-auto px-4">
          <Link href="/services" className="inline-flex items-center gap-1.5 text-emerald-100 hover:text-white text-sm mb-5"><ArrowLeft size={16} aria-hidden /> All services</Link>
          <div className="flex flex-wrap gap-2 mb-3">
            {svc.department_name && <span className="badge badge-blue max-w-full truncate" title={svc.department_name}>{svc.department_name}</span>}
            {svc.category && <span className="badge badge-slate capitalize">{svc.category.replace(/_/g, " ")}</span>}
            <VerificationBadge status={svc.verification_status} />
          </div>
          <h1 className="text-2xl md:text-3xl font-black" data-testid="service-name">{svc.name}</h1>
          {svc.name_ta && <p className="text-emerald-100 font-tamil text-lg mt-1">{svc.name_ta}</p>}
        </div>
      </div>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-5">
        <section className="card p-6" aria-labelledby="about-h">
          <h2 id="about-h" className="font-bold text-slate-900 mb-2">About this service</h2>
          <p className="text-slate-700 leading-relaxed">{svc.description || "No description is recorded for this service."}</p>
          {svc.notes && <p className="text-sm text-slate-600 mt-3">Legal basis recorded: <span className="font-mono">{svc.notes}</span></p>}
        </section>

        <section className="card p-6" aria-labelledby="fees-h" data-testid="fees-section">
          <h2 id="fees-h" className="font-bold text-slate-900 mb-3">Fees and processing time</h2>
          {svc.charges_verified ? (
            <dl className="grid sm:grid-cols-3 gap-4 text-sm">
              <div><dt className="text-slate-500">Government fee</dt><dd className="font-semibold text-slate-900">{svc.government_fee == null ? "Not stated" : money(svc.government_fee)}</dd></div>
              <div><dt className="text-slate-500">Service charge</dt><dd className="font-semibold text-slate-900">{svc.service_charge == null ? "Not stated" : money(svc.service_charge)}</dd></div>
              <div><dt className="text-slate-500">Processing time</dt><dd className="font-semibold text-slate-900">{svc.processing_time || "Not stated"}</dd></div>
            </dl>
          ) : (
            <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900" data-testid="charges-unconfirmed-detail">
              The fee, service charge and processing time for this service have <b>not been confirmed</b> against an official source, so they are not shown here.
              Please ask the department or your nearest e-Sevai centre.
            </p>
          )}
        </section>

        <section className="card p-6" aria-labelledby="docs-h" data-testid="requirements-section">
          <h2 id="docs-h" className="font-bold text-slate-900 mb-3">Documents required</h2>
          {reqs.length === 0 ? (
            <p className="text-sm text-slate-600">No document list has been recorded for this service yet.</p>
          ) : (
            <ul className="space-y-2">
              {reqs.map((r) => (
                <li key={r.requirement_id} className="flex items-start gap-2 text-sm">
                  <FileText size={14} className="mt-1 text-slate-500 shrink-0" aria-hidden />
                  <span><b>{r.document_type}</b>{r.mandatory === false ? " (optional)" : ""}{r.description ? ` — ${r.description}` : ""}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card p-6 space-y-3" aria-labelledby="apply-h" data-testid="apply-section">
          <h2 id="apply-h" className="font-bold text-slate-900">How to apply</h2>
          <p className="text-sm text-slate-700">MyGovt does not take applications. Use the official portal below, or visit an e-Sevai centre.</p>
          <div className="flex flex-wrap gap-3">
            {svc.application_url && (
              <a href={svc.application_url} target="_blank" rel="noopener noreferrer" className="btn-primary" data-testid="apply-link">
                Apply on the official site <ExternalLink size={14} aria-hidden /><span className="sr-only"> (opens an external website)</span>
              </a>
            )}
            {svc.official_source_url && (
              <a href={svc.official_source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary">
                Official source <ExternalLink size={14} aria-hidden /><span className="sr-only"> (opens an external website)</span>
              </a>
            )}
            {!svc.application_url && !svc.official_source_url && <p className="text-sm text-slate-600">No official link is recorded for this service.</p>}
          </div>
        </section>

        <section className="card p-6 text-sm" aria-labelledby="src-h" data-testid="source-info">
          <h2 id="src-h" className="font-bold text-slate-900 mb-2">Source and verification</h2>
          <p className="text-slate-700">
            {verified
              ? <>Verified against: <span className="font-mono">{svc.source_document_ref}</span></>
              : <>Not yet verified against an official document.{svc.source_document_ref ? <> The dataset asserts <span className="font-mono">{svc.source_document_ref}</span>, which has <b>not</b> been confirmed.</> : " No source document is recorded."}</>}
          </p>
        </section>
      </main>
    </div>
  );
}
