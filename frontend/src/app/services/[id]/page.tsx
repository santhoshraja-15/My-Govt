"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ExternalLink, FileText, Loader2 } from "lucide-react";
import { services as servicesAPI } from "@/lib/api";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { ErrorState } from "@/components/ui/AsyncState";
import { useLang } from "@/lib/i18n";

export default function ServiceDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, label, dept, names, pickL, fmtDate, fmtNumber } = useLang();
  const [svc, setSvc] = useState<any>(null);
  const [state, setState] = useState<"loading" | "ok" | "missing" | "error">("loading");

  const load = useCallback(() => {
    setState("loading");
    servicesAPI.get(id).then((s) => { setSvc(s); setState("ok"); })
      .catch((e) => { if (e?.status === 404 || e?.status === 422) setState("missing"); else setState("error"); });
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const money = (n: number) => `₹${fmtNumber(n)}`;   // 0 is the e-Sevai application fee, not "free": a service charge may still apply

  if (state === "loading") return <div className="min-h-[60vh] flex items-center justify-center" role="status" aria-label={t("service.loading")}><Loader2 size={32} className="animate-spin text-brand-600" /></div>;
  if (state === "error") return <main className="max-w-3xl mx-auto px-4 py-16"><ErrorState message={t("common.loadFailed")} onRetry={load} /></main>;
  if (state === "missing") {
    return (
      <main className="max-w-3xl mx-auto px-4 py-20 text-center space-y-3" data-testid="service-not-found">
        <FileText size={44} className="text-slate-400 mx-auto" aria-hidden />
        <h1 className="text-xl font-bold text-slate-800">{t("service.notFoundTitle")}</h1>
        <p className="text-slate-600">{t("service.notFoundText")}</p>
        <Link href="/services" className="btn-secondary">{t("service.backToList")}</Link>
      </main>
    );
  }

  const nm = names(svc.name, svc.name_ta);
  const desc = pickL(svc.description, svc.description_ta);
  const reqs: any[] = svc.requirements ?? [];
  const official = reqs.length > 0 && reqs.every((r) => r.requirement_level === "required");
  const compiled = reqs.length > 0 && !official;
  const verified = svc.verification_status === "official_verified";
  const listed = svc.fee_status === "listed_official_2023";
  const steps: string[] = svc.application_steps ?? [];
  const eligibility: string[] = svc.eligibility_points ?? [];
  const sources: { url: string; label: string }[] = svc.source_urls ?? [];
  const showFees = svc.charges_verified || listed || svc.fee_note;

  return (
    <div className="min-h-screen bg-slate-50" data-testid="service-detail">
      <div className="bg-gradient-to-r from-emerald-800 to-teal-700 text-white py-10">
        <div className="max-w-4xl mx-auto px-4">
          <Link href="/services" className="inline-flex items-center gap-1.5 text-emerald-100 hover:text-white text-sm mb-5"><ArrowLeft size={16} aria-hidden /> {t("service.allServices")}</Link>
          <div className="flex flex-wrap gap-2 mb-3">
            {svc.department_name && <span className="badge badge-blue max-w-full truncate" title={dept(svc.department_name)}>{dept(svc.department_name)}</span>}
            {svc.category && <span className="badge badge-slate">{label("cat", svc.category)}</span>}
            <VerificationBadge status={svc.verification_status} />
          </div>
          <h1 className="text-2xl md:text-3xl font-black" data-testid="service-name">{nm.primary}</h1>
          {nm.secondary && <p className="text-emerald-100 text-lg mt-1" data-testid="service-secondary-name" data-i18n-skip lang={nm.secondaryLang}>{nm.secondary}</p>}
        </div>
      </div>

      <main className="max-w-4xl mx-auto px-4 py-6 space-y-5">
        <section className="card p-6" aria-labelledby="about-h">
          <h2 id="about-h" className="font-bold text-slate-900 mb-2">{t("service.about")}</h2>
          <p className="text-slate-700 leading-relaxed" lang={desc.text ? desc.lang : undefined}>{desc.text || t("service.noDescription")}</p>
          {svc.responsible_department && <p className="text-sm text-slate-700 mt-3"><b>{t("service.responsible")}:</b> <span lang="en">{svc.responsible_department}</span></p>}
          {svc.notes && <p className="text-sm text-slate-600 mt-3" lang="en">{svc.notes}</p>}
          {svc.applicable_rules && <p className="text-sm text-slate-600 mt-2">{t("service.legalBasis")} <span className="font-mono" lang="en">{svc.applicable_rules}</span></p>}
          {eligibility.length > 0 && (
            <div className="mt-4" data-testid="service-eligibility">
              <h3 className="text-sm font-semibold text-slate-900 mb-1">{t("service.eligibility")}</h3>
              <ul className="list-disc pl-5 text-sm text-slate-700 space-y-1" lang="en">{eligibility.map((e, i) => <li key={i}>{e}</li>)}</ul>
            </div>
          )}
        </section>

        <section className="card p-6" aria-labelledby="fees-h" data-testid="fees-section">
          <h2 id="fees-h" className="font-bold text-slate-900 mb-3">{t("service.feesTitle")}</h2>
          {showFees ? (
            <>
              {(svc.government_fee != null || svc.service_charge != null || svc.processing_time) && (
                <dl className="grid sm:grid-cols-3 gap-4 text-sm">
                  <div><dt className="text-slate-500">{t("service.govFee")}</dt><dd className="font-semibold text-slate-900">{svc.government_fee == null ? t("common.notStated") : money(svc.government_fee)}</dd></div>
                  <div><dt className="text-slate-500">{t("service.serviceCharge")}</dt><dd className="font-semibold text-slate-900">{svc.service_charge == null ? t("common.notStated") : money(svc.service_charge)}</dd></div>
                  <div><dt className="text-slate-500">{t("service.processing")}</dt><dd className="font-semibold text-slate-900" lang="en">{svc.processing_time || t("service.feeUnconfirmed")}</dd></div>
                </dl>
              )}
              {svc.fee_note && <p className="text-sm text-slate-700 mt-3" lang="en" data-testid="fee-note">{svc.fee_note}</p>}
              {!svc.processing_time && svc.processing_time_note && (svc.government_fee != null || svc.service_charge != null) && (
                <p className="text-xs text-slate-500 mt-2">{t("service.processing")}: {t("service.feeUnconfirmed")}</p>
              )}
              <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900 mt-3" data-testid="charges-listed-note">{t("service.listedNote")}</p>
            </>
          ) : (
            <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900" data-testid="charges-unconfirmed-detail">{t("service.feeUnconfirmedLong")}</p>
          )}
        </section>

        <section className="card p-6" aria-labelledby="docs-h" data-testid="requirements-section">
          <h2 id="docs-h" className="font-bold text-slate-900 mb-3">{t("service.docsTitle")}</h2>
          {reqs.length === 0 ? (
            <p className="text-sm text-slate-700" data-testid="docs-unverified">{t("service.docsNone")}</p>
          ) : (
            <>
              <p className={`text-xs mb-3 ${official ? "text-emerald-700" : "text-amber-900 rounded-xl bg-amber-50 border border-amber-200 p-3"}`} data-testid={official ? "docs-official-note" : "docs-compiled-note"}>
                {official ? t("service.docsOfficial") : t("service.docsUnverified")}
              </p>
              <ul className="space-y-2" lang="en">
                {reqs.map((r) => (
                  <li key={r.requirement_id} className="flex items-start gap-2 text-sm" data-level={r.requirement_level}>
                    <FileText size={14} className="mt-1 text-slate-500 shrink-0" aria-hidden />
                    <span>
                      <b>{r.document_type}</b>
                      {r.requirement_level && r.requirement_level !== "required" && <span className="ml-2 text-xs text-slate-500" lang={undefined}>[{label("doclevel", r.requirement_level)}]</span>}
                      {r.description && !(official) ? ` — ${r.description}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
              {compiled && <span hidden />}
            </>
          )}
        </section>

        <section className="card p-6 space-y-3" aria-labelledby="apply-h" data-testid="apply-section">
          <h2 id="apply-h" className="font-bold text-slate-900">{t("service.applyTitle")}</h2>
          <p className="text-sm text-slate-700">{t("service.applyNote")}</p>
          {svc.how_to_apply && <p className="text-sm text-slate-700" lang="en">{svc.how_to_apply}</p>}
          {steps.length > 0 && (
            <div data-testid="application-steps">
              <h3 className="text-sm font-semibold text-slate-900 mb-1">{t("service.steps")}</h3>
              <ol className="list-decimal pl-5 text-sm text-slate-700 space-y-1" lang="en">{steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
            </div>
          )}
          <div className="flex flex-wrap gap-3">
            {svc.application_url && (
              <a href={svc.application_url} target="_blank" rel="noopener noreferrer" className="btn-primary" data-testid="apply-link" title={t("common.leavingNotice")}>
                {t("service.apply")} <ExternalLink size={14} aria-hidden /><span className="sr-only"> {t("common.opensExternal")}</span>
              </a>
            )}
            {svc.official_source_url && svc.official_source_url !== svc.application_url && (
              <a href={svc.official_source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary" title={t("common.leavingNotice")}>
                {t("service.officialSource")} <ExternalLink size={14} aria-hidden /><span className="sr-only"> {t("common.opensExternal")}</span>
              </a>
            )}
            {!svc.application_url && !svc.official_source_url && <p className="text-sm text-slate-600">{t("service.noLink")}</p>}
          </div>
        </section>

        <section className="card p-6 text-sm" aria-labelledby="src-h" data-testid="source-info">
          <h2 id="src-h" className="font-bold text-slate-900 mb-2">{t("service.sourceTitle")}</h2>
          <p className="text-slate-700">
            {verified
              ? <>{t("scheme.verifiedAgainst")} <span className="font-mono">{svc.source_document_ref}</span></>
              : <>{t("scheme.notVerified")}{svc.source_document_ref ? <> {t("scheme.assertsPre")} <span className="font-mono">{svc.source_document_ref}</span>{t("scheme.assertsPost")}</> : ` ${t("scheme.noSourceDoc")}`}</>}
          </p>
          {svc.last_checked_on && <p className="text-xs text-slate-500 mt-2">{t("service.lastChecked", { date: fmtDate(svc.last_checked_on) })}</p>}
          {sources.length > 0 && (
            <div className="mt-3" data-testid="service-sources">
              <p className="text-xs font-semibold text-slate-600 mb-1">{t("service.sourcesConsulted")}</p>
              <ul className="space-y-1 text-xs">
                {sources.map((s) => (
                  <li key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer" className="text-brand-700 underline break-all" lang="en">{s.label || s.url}</a><span className="sr-only"> {t("common.opensExternal")}</span></li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
