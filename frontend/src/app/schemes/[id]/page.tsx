"use client";

import { useState, useEffect, use } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle, AlertCircle, ExternalLink, Award, FileText, Shield, Loader2, ListChecks, Ban } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { EligibilityChecker } from "@/components/schemes/EligibilityChecker";
import { useLang, type TKey } from "@/lib/i18n";

function RuleBadge({ outcome }: { outcome: string }) {
  const { t } = useLang();
  const meta: Record<string, { key: TKey; icon: React.ReactNode }> = {
    PASS: { key: "scheme.rule.pass", icon: <CheckCircle2 size={14} className="text-emerald-600 shrink-0" aria-hidden /> },
    FAIL: { key: "scheme.rule.fail", icon: <XCircle size={14} className="text-red-600 shrink-0" aria-hidden /> },
    UNKNOWN: { key: "scheme.rule.unknown", icon: <AlertCircle size={14} className="text-amber-700 shrink-0" aria-hidden /> },
  };
  const m = meta[outcome] ?? { key: "scheme.rule.unchecked" as TKey, icon: <AlertCircle size={14} className="text-slate-500 shrink-0" aria-hidden /> };
  return <span title={t(m.key)}>{m.icon}<span className="sr-only">{t(m.key)}</span></span>;
}

/** Government-sourced prose that has no Tamil version is rendered in English and marked lang="en". */
function EnglishList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2 text-sm text-slate-700 list-disc pl-5" lang="en">
      {items.map((x, i) => <li key={i}>{x}</li>)}
    </ul>
  );
}

export default function SchemeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { t, lang, label, dept, names, pickL, fmtDate, fmtNumber } = useLang();
  const [scheme, setScheme] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "eligibility" | "documents" | "benefits">("overview");
  const [check, setCheck] = useState<any>(null);

  useEffect(() => {
    schemesAPI.get(id).then(setScheme).catch(() => setScheme(null)).finally(() => setLoading(false));
  }, [id]);
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get("tab");
    if (q === "eligibility" || q === "benefits" || q === "documents") setTab(q);
  }, []);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 size={32} className="animate-spin text-brand-600" />
    </div>
  );

  if (!scheme) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4">
      <Award size={48} className="text-slate-300" />
      <h2 className="font-bold text-slate-600">{t("scheme.notFound")}</h2>
      <Link href="/schemes" className="btn-secondary">{t("scheme.backToList")}</Link>
    </div>
  );

  const nm = names(scheme.name, scheme.name_ta);
  const short = pickL(scheme.description, scheme.description_ta);
  const full: string | null = scheme.full_description && scheme.full_description !== scheme.description ? scheme.full_description : null;
  const eligPoints: string[] = scheme.eligibility_points ?? [];
  const exclPoints: string[] = scheme.exclusion_points ?? [];
  const steps: string[] = scheme.application_steps ?? [];
  const sources: { url: string; label: string }[] = scheme.source_urls ?? [];
  const evidence: Record<string, any> = scheme.field_evidence ?? {};
  const officialFields = Object.keys(evidence).length;
  const hasLongContent = !!(eligPoints.length || exclPoints.length || steps.length || full || scheme.purpose);

  const TABS = [
    { key: "overview", label: t("scheme.tab.overview") },
    { key: "eligibility", label: t("scheme.tab.eligibility", { n: (scheme.eligibility_rules?.length || 0) + eligPoints.length }) },
    { key: "benefits", label: t("scheme.tab.benefits", { n: scheme.benefits?.length || 0 }) },
    { key: "documents", label: t("scheme.tab.documents", { n: scheme.required_documents?.length || 0 }) },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-brand-900 to-brand-700 text-white py-10">
        <div className="max-w-4xl mx-auto px-4">
          <Link href="/schemes" className="inline-flex items-center gap-1.5 text-blue-200 hover:text-white text-sm mb-5 transition-colors">
            <ArrowLeft size={16} /> {t("scheme.allSchemes")}
          </Link>
          <div className="flex flex-wrap gap-3 mb-3">
            {scheme.department_name && <span className="badge badge-blue max-w-full truncate" title={dept(scheme.department_name)}>{dept(scheme.department_name)}</span>}
            {scheme.category && <span className="badge badge-slate">{label("cat", scheme.category)}</span>}
            <span className="badge badge-green">{label("level", scheme.scheme_level)}</span>
            <VerificationBadge status={scheme.verification_status} />
          </div>
          <h1 className="text-2xl md:text-3xl font-black mb-2" data-testid="scheme-name">{nm.primary}</h1>
          {nm.secondary && <p className="text-blue-100 text-lg" data-testid="scheme-secondary-name" data-i18n-skip lang={nm.secondaryLang}>{nm.secondary}</p>}
          <button type="button" className="btn-primary bg-saffron-500 hover:bg-saffron-600 mt-4" data-testid="check-my-eligibility" onClick={() => { setTab("eligibility"); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
            {t("scheme.checkEligibility")}
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        <div role="tablist" aria-label={t("scheme.sections")} className="flex gap-1 bg-white rounded-xl p-1 border border-slate-200 mb-6 overflow-x-auto">
          {TABS.map((x) => (
            <button key={x.key} role="tab" aria-selected={tab === x.key} data-testid={`scheme-tab-${x.key}`} onClick={() => setTab(x.key as any)}
              className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                tab === x.key ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"}`}>
              {x.label}
            </button>
          ))}
        </div>

        {lang === "ta" && hasLongContent && (
          <p className="mb-4 rounded-xl bg-slate-100 border border-slate-200 p-3 text-xs text-slate-700" data-testid="english-only-note">{t("scheme.contentEnglishOnly")}</p>
        )}

        {tab === "overview" && (
          <div className="space-y-5 animate-fade-in">
            <div className="card p-6">
              <h2 className="font-bold text-slate-900 mb-3">{t("scheme.about")}</h2>
              <p className="text-slate-600 leading-relaxed" lang={short.lang}>{short.text}</p>
              {full && <p className="text-slate-600 leading-relaxed mt-3" lang="en">{full}</p>}
              {scheme.purpose && <p className="text-sm text-slate-700 mt-3"><b>{t("scheme.purpose")}:</b> <span lang="en">{scheme.purpose}</span></p>}
              {scheme.implementing_department && <p className="text-sm text-slate-700 mt-1"><b>{t("scheme.implementedBy")}:</b> <span lang="en">{scheme.implementing_department}</span></p>}
              {scheme.benefits_summary && <p className="text-sm text-emerald-700 font-medium mt-3" lang="en" data-testid="benefits-summary">{scheme.benefits_summary}</p>}
              {scheme.notes && <p className="text-slate-500 text-sm mt-3 italic" lang="en">{scheme.notes}</p>}
            </div>

            {(steps.length > 0 || scheme.how_to_apply_note) && (
              <div className="card p-6" data-testid="how-to-apply">
                <h2 className="font-bold text-slate-900 mb-3 flex items-center gap-2"><ListChecks size={18} aria-hidden /> {t("scheme.howToApply")}</h2>
                {steps.length > 0 && <ol className="list-decimal pl-5 space-y-1.5 text-sm text-slate-700" lang="en">{steps.map((s, i) => <li key={i}>{s}</li>)}</ol>}
                {scheme.how_to_apply_note && <p className="text-sm text-slate-600 mt-3" lang="en">{scheme.how_to_apply_note}</p>}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {scheme.effective_from && (
                <div className="card p-4">
                  <p className="text-xs text-slate-500 mb-1">{t("scheme.effectiveFrom")}</p>
                  <p className="font-semibold text-slate-800">{fmtDate(scheme.effective_from)}</p>
                </div>
              )}
              {scheme.scheme_code && (
                <div className="card p-4">
                  <p className="text-xs text-slate-500 mb-1">{t("scheme.code")}</p>
                  <p className="font-mono font-semibold text-slate-800">{scheme.scheme_code}</p>
                </div>
              )}
              <div className="card p-4 sm:col-span-2" data-testid="source-info">
                <p className="text-xs text-slate-500 mb-1">{t("scheme.sourceTitle")}</p>
                <p className="text-sm text-slate-700">
                  {scheme.verification_status === "official_verified"
                    ? <>{t("scheme.verifiedAgainst")} <span className="font-mono" lang="en">{scheme.source_document_ref}</span></>
                    : <>{t("scheme.notVerified")}{scheme.source_document_ref ? <> {t("scheme.assertsPre")} <span className="font-mono">{scheme.source_document_ref}</span>{t("scheme.assertsPost")}</> : ` ${t("scheme.noSourceDoc")}`} {t("scheme.confirmWithDept")}</>}
                </p>
                {scheme.last_checked_on && <p className="text-xs text-slate-500 mt-2">{t("scheme.lastChecked", { date: fmtDate(scheme.last_checked_on) })}</p>}
                {hasLongContent && <p className="text-xs text-amber-800 mt-2" data-testid="content-notice">{t("scheme.contentNotice")}</p>}
                {sources.length > 0 && (
                  <div className="mt-3" data-testid="scheme-sources">
                    <p className="text-xs font-semibold text-slate-600 mb-1">{t("scheme.sources")}</p>
                    <ul className="space-y-1 text-xs">
                      {sources.map((s) => (
                        <li key={s.url}><a href={s.url} target="_blank" rel="noopener noreferrer" className="text-brand-700 underline break-all" lang="en">{s.label || s.url}</a><span className="sr-only"> {t("common.opensExternal")}</span></li>
                      ))}
                    </ul>
                  </div>
                )}
                {officialFields > 0 && <p className="text-xs text-emerald-700 mt-2">{t("scheme.fieldOfficial")}: {Object.keys(evidence).join(", ")}</p>}
              </div>
            </div>

            {(scheme.application_url || scheme.official_source_url) && (
              <div className="card p-5 flex flex-wrap gap-3">
                {scheme.application_url && (
                  <a href={scheme.application_url} target="_blank" rel="noopener noreferrer" className="btn-primary" title={t("common.leavingNotice")}>
                    {t("scheme.apply")} <ExternalLink size={14} aria-hidden /><span className="sr-only"> {t("common.opensExternal")}</span>
                  </a>
                )}
                {scheme.official_source_url && (
                  <a href={scheme.official_source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary" title={t("common.leavingNotice")}>
                    {t("scheme.officialSource")} <ExternalLink size={14} aria-hidden /><span className="sr-only"> {t("common.opensExternal")}</span>
                  </a>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "eligibility" && (
          <div className="space-y-4 animate-fade-in">
            <EligibilityChecker scheme={scheme} onResult={setCheck} />

            {eligPoints.length > 0 && (
              <div className="card p-5" data-testid="eligibility-points">
                <h3 className="font-bold text-slate-900 mb-3 flex items-center gap-2"><ListChecks size={16} aria-hidden /> {t("scheme.eligibilityConditions")}</h3>
                <EnglishList items={eligPoints} />
              </div>
            )}
            {exclPoints.length > 0 && (
              <div className="card p-5 border-red-100" data-testid="exclusion-points">
                <h3 className="font-bold text-slate-900 mb-3 flex items-center gap-2"><Ban size={16} aria-hidden /> {t("scheme.exclusions")}</h3>
                <EnglishList items={exclPoints} />
              </div>
            )}

            {!scheme.eligibility_rules?.length ? (
              eligPoints.length === 0 && (
                <div className="card p-8 text-center text-slate-500">
                  <Shield size={36} className="mx-auto mb-2 opacity-40" />
                  <p>{t("scheme.noRules")}</p>
                </div>
              )
            ) : (
              <>
                {scheme.eligibility_rules.some((r: any) => String(r.source_reference || "").startsWith("DEMO RULE")) ? (
                  <div className="card p-4 bg-amber-50 border-amber-200 text-sm text-amber-800" data-testid="demo-rules-banner">
                    <b>{t("scheme.demoBannerTitle")}</b> {t("scheme.demoBannerText")}
                  </div>
                ) : (
                  <div className="card p-4 bg-blue-50 border-blue-100 text-sm text-blue-700">{t("scheme.rulesBanner")}</div>
                )}
                {Object.entries(
                  scheme.eligibility_rules.reduce((acc: any, rule: any) => {
                    const g = rule.rule_group || 1;
                    acc[g] = acc[g] || [];
                    acc[g].push(rule);
                    return acc;
                  }, {})
                ).map(([group, rules]: any) => (
                  <div key={group} className="card p-5">
                    <p className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">{t("scheme.group", { n: group })}</p>
                    <div className="space-y-3">
                      {rules.map((rule: any) => {
                        const text = pickL(rule.human_readable, rule.human_readable_ta);
                        return (
                          <div key={rule.rule_id} className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
                            <RuleBadge outcome={(check?.rule_results ?? []).find((r: any) => r.rule_id === rule.rule_id)?.outcome ?? "UNCHECKED"} />
                            <div className="flex-1">
                              <p className="text-sm font-medium text-slate-800" lang={text.lang}>{text.text}</p>
                              {rule.source_reference && <p className="text-xs text-slate-500 mt-1">{t("scheme.source")} <span lang="en">{rule.source_reference}</span></p>}
                            </div>
                            <span className={`badge ${rule.mandatory ? "badge-red" : "badge-slate"} shrink-0`}>
                              {rule.mandatory ? t("scheme.mandatory") : t("scheme.optional")}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </>
            )}
          </div>
        )}

        {tab === "benefits" && (
          <div className="space-y-4 animate-fade-in">
            {!scheme.benefits?.length ? (
              <div className="card p-8 text-center text-slate-500">
                <Award size={36} className="mx-auto mb-2 opacity-40" />
                <p>{t("scheme.noBenefits")}</p>
              </div>
            ) : (
              scheme.benefits.map((b: any) => (
                <div key={b.benefit_id} className="card p-5 flex items-start gap-4" data-testid="benefit-card">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0">
                    <Award size={18} className="text-emerald-600" />
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wide mb-0.5">{label("benefit.type", b.benefit_type)}</p>
                    <p className="font-semibold text-slate-800" lang="en">{b.description}</p>
                    {b.amount != null && (
                      <p className="text-emerald-700 font-bold mt-1" data-testid="benefit-amount">
                        ₹{fmtNumber(b.amount)}{b.frequency ? ` ${label("benefit.freq", b.frequency)}` : ""}
                      </p>
                    )}
                    {b.amount_status && <p className="text-xs text-amber-800 mt-1" data-testid="benefit-amount-status" data-status={b.amount_status}>{label("benefit.amountStatus", b.amount_status)}</p>}
                    {b.conditions && <p className="text-xs text-slate-500 mt-1" lang="en">{b.conditions}</p>}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {tab === "documents" && (
          <div className="space-y-4 animate-fade-in">
            {!scheme.required_documents?.length ? (
              <div className="card p-8 text-center text-slate-500">
                <FileText size={36} className="mx-auto mb-2 opacity-40" />
                <p>{t("scheme.noDocuments")}</p>
              </div>
            ) : (
              <>
                {scheme.required_documents.some((d: any) => d.requirement_level === "unverified") && (
                  <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900" data-testid="docs-unverified-note">{t("scheme.docsUnverifiedNote")}</p>
                )}
                {scheme.required_documents.map((d: any, i: number) => (
                  <div key={d.requirement_id} className="card p-4 flex items-start gap-4" data-testid="scheme-document" data-level={d.requirement_level}>
                    <div className="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center shrink-0 text-xs font-bold text-brand-600">{i + 1}</div>
                    <div className="flex-1">
                      <p className="font-semibold text-slate-800 text-sm" lang="en">{d.document_type}</p>
                      {d.description && <p className="text-xs text-slate-500 mt-0.5" lang="en">{d.description}</p>}
                    </div>
                    <span className={`badge ${d.requirement_level === "required" ? "badge-red" : d.requirement_level === "unverified" ? "badge-yellow" : "badge-slate"} shrink-0`}>
                      {label("doclevel", d.requirement_level ?? (d.mandatory ? "required" : "recommended"))}
                    </span>
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
