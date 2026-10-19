"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle, AlertCircle, ExternalLink, Award, FileText, Shield, Loader2 } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";
import { use } from "react";
import { VerificationBadge } from "@/components/ui/VerificationBadge";
import { EligibilityChecker } from "@/components/schemes/EligibilityChecker";

function RuleBadge({ outcome }: { outcome: string }) {
  if (outcome === "PASS") return <span title="You meet this criterion"><CheckCircle2 size={14} className="text-emerald-600 shrink-0" aria-hidden /><span className="sr-only">You meet this criterion</span></span>;
  if (outcome === "FAIL") return <span title="You do not meet this criterion"><XCircle size={14} className="text-red-600 shrink-0" aria-hidden /><span className="sr-only">You do not meet this criterion</span></span>;
  if (outcome === "UNKNOWN") return <span title="Unknown: not enough information"><AlertCircle size={14} className="text-amber-700 shrink-0" aria-hidden /><span className="sr-only">Unknown: not enough information</span></span>;
  return <span title="Not checked yet"><AlertCircle size={14} className="text-slate-500 shrink-0" aria-hidden /><span className="sr-only">Not checked yet</span></span>;
}

export default function SchemeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [scheme, setScheme] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "eligibility" | "documents" | "benefits">("overview");
  const [check, setCheck] = useState<any>(null);

  useEffect(() => {
    schemesAPI.get(id).then(setScheme).catch(() => setScheme(null)).finally(() => setLoading(false));
  }, [id]);
  useEffect(() => {
    const t = new URLSearchParams(window.location.search).get("tab");
    if (t === "eligibility" || t === "benefits" || t === "documents") setTab(t);
  }, []);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 size={32} className="animate-spin text-brand-600" />
    </div>
  );

  if (!scheme) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4">
      <Award size={48} className="text-slate-300" />
      <h2 className="font-bold text-slate-600">Scheme not found</h2>
      <Link href="/schemes" className="btn-secondary">Back to Schemes</Link>
    </div>
  );

  const TABS = [
    { key: "overview", label: "Overview" },
    { key: "eligibility", label: `Eligibility (${scheme.eligibility_rules?.length || 0})` },
    { key: "benefits", label: `Benefits (${scheme.benefits?.length || 0})` },
    { key: "documents", label: `Documents Required (${scheme.required_documents?.length || 0})` },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-gradient-to-r from-brand-900 to-brand-700 text-white py-10">
        <div className="max-w-4xl mx-auto px-4">
          <Link href="/schemes" className="inline-flex items-center gap-1.5 text-blue-200 hover:text-white text-sm mb-5 transition-colors">
            <ArrowLeft size={16} /> All Schemes
          </Link>
          <div className="flex flex-wrap gap-3 mb-3">
            {scheme.department_name && <span className="badge badge-blue max-w-full truncate" title={scheme.department_name}>{scheme.department_name}</span>}
            {scheme.category && <span className="badge badge-slate capitalize">{scheme.category.replace(/_/g," ")}</span>}
            <span className="badge badge-green capitalize">{scheme.scheme_level}</span>
            <VerificationBadge status={scheme.verification_status} />
          </div>
          <h1 className="text-2xl md:text-3xl font-black mb-2">{scheme.name}</h1>
          {scheme.name_ta && <p className="text-blue-100 font-tamil text-lg">{scheme.name_ta}</p>}
          <button type="button" className="btn-primary bg-saffron-500 hover:bg-saffron-600 mt-4" data-testid="check-my-eligibility" onClick={() => { setTab("eligibility"); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
            Check my eligibility
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div role="tablist" aria-label="Scheme sections" className="flex gap-1 bg-white rounded-xl p-1 border border-slate-200 mb-6 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} data-testid={`scheme-tab-${t.key}`} onClick={() => setTab(t.key as any)}
              className={`px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                tab === t.key ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"}`}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "overview" && (
          <div className="space-y-5 animate-fade-in">
            <div className="card p-6">
              <h2 className="font-bold text-slate-900 mb-3">About this Scheme</h2>
              <p className="text-slate-600 leading-relaxed">{scheme.description}</p>
              {scheme.notes && <p className="text-slate-500 text-sm mt-3 italic">{scheme.notes}</p>}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {scheme.effective_from && (
                <div className="card p-4">
                  <p className="text-xs text-slate-500 mb-1">Effective From</p>
                  <p className="font-semibold text-slate-800">{new Date(scheme.effective_from).toLocaleDateString("en-IN")}</p>
                </div>
              )}
              {scheme.scheme_code && (
                <div className="card p-4">
                  <p className="text-xs text-slate-500 mb-1">Scheme Code</p>
                  <p className="font-mono font-semibold text-slate-800">{scheme.scheme_code}</p>
                </div>
              )}
              <div className="card p-4 sm:col-span-2" data-testid="source-info">
                <p className="text-xs text-slate-500 mb-1">Source and verification</p>
                <p className="text-sm text-slate-700">
                  {scheme.verification_status === "official_verified"
                    ? <>Verified against: <span className="font-mono">{scheme.source_document_ref}</span></>
                    : <>Not yet verified against an official document.{scheme.source_document_ref ? <> The dataset asserts <span className="font-mono">{scheme.source_document_ref}</span>, which has <b>not</b> been confirmed.</> : " No source document is recorded."} Confirm with the department before acting.</>}
                </p>
              </div>
            </div>

            {(scheme.application_url || scheme.official_source_url) && (
              <div className="card p-5 flex flex-wrap gap-3">
                {scheme.application_url && (
                  <a href={scheme.application_url} target="_blank" rel="noopener noreferrer" className="btn-primary">
                    Apply on the official site <ExternalLink size={14} aria-hidden /><span className="sr-only"> (opens an external website)</span>
                  </a>
                )}
                {scheme.official_source_url && (
                  <a href={scheme.official_source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary">
                    Official source <ExternalLink size={14} aria-hidden /><span className="sr-only"> (opens an external website)</span>
                  </a>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "eligibility" && (
          <div className="space-y-4 animate-fade-in">
            <EligibilityChecker scheme={scheme} onResult={setCheck} />
            {!scheme.eligibility_rules?.length ? (
              <div className="card p-8 text-center text-slate-500">
                <Shield size={36} className="mx-auto mb-2 opacity-40" />
                <p>No eligibility rules defined for this scheme yet.</p>
              </div>
            ) : (
              <>
                {scheme.eligibility_rules.some((r: any) => String(r.source_reference || "").startsWith("DEMO RULE")) ? (
                  <div className="card p-4 bg-amber-50 border-amber-200 text-sm text-amber-800" data-testid="demo-rules-banner">
                    <b>Demonstration rules.</b> These criteria are illustrative examples for this demo, not the scheme&apos;s official eligibility conditions.
                    Rules in the same group (AND logic) must all pass.
                  </div>
                ) : (
                  <div className="card p-4 bg-blue-50 border-blue-100 text-sm text-blue-700">
                    Eligibility criteria as recorded in this platform (confirm with the department before applying).
                    Rules in the same group (AND logic) must all pass.
                  </div>
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
                    <p className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">
                      Criteria Group {group}
                    </p>
                    <div className="space-y-3">
                      {rules.map((rule: any) => (
                        <div key={rule.rule_id} className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
                          <RuleBadge outcome={(check?.rule_results ?? []).find((r: any) => r.rule_id === rule.rule_id)?.outcome ?? "UNCHECKED"} />
                          <div className="flex-1">
                            <p className="text-sm font-medium text-slate-800">{rule.human_readable}</p>
                            {rule.human_readable_ta && (
                              <p className="text-xs text-slate-500 font-tamil mt-0.5">{rule.human_readable_ta}</p>
                            )}
                            {rule.source_reference && (
                              <p className="text-xs text-slate-500 mt-1">Source: {rule.source_reference}</p>
                            )}
                          </div>
                          <span className={`badge ${rule.mandatory ? "badge-red" : "badge-slate"} shrink-0`}>
                            {rule.mandatory ? "Mandatory" : "Optional"}
                          </span>
                        </div>
                      ))}
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
                <p>Benefit details not yet available.</p>
              </div>
            ) : (
              scheme.benefits.map((b: any) => (
                <div key={b.benefit_id} className="card p-5 flex items-start gap-4">
                  <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0">
                    <Award size={18} className="text-emerald-600" />
                  </div>
                  <div>
                    <p className="text-xs text-slate-500 uppercase tracking-wide mb-0.5">{b.benefit_type?.replace(/_/g," ")}</p>
                    <p className="font-semibold text-slate-800">{b.description}</p>
                    {b.amount && <p className="text-emerald-600 font-bold mt-1">₹{b.amount.toLocaleString("en-IN")}{b.unit ? ` / ${b.unit}` : ""}</p>}
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
                <p>Document requirements not yet listed.</p>
              </div>
            ) : (
              scheme.required_documents.map((d: any, i: number) => (
                <div key={d.requirement_id} className="card p-4 flex items-start gap-4">
                  <div className="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center shrink-0 text-xs font-bold text-brand-600">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-slate-800 text-sm">{d.document_type}</p>
                    {d.description && <p className="text-xs text-slate-500 mt-0.5">{d.description}</p>}
                  </div>
                  <span className={`badge ${d.mandatory ? "badge-red" : "badge-slate"} shrink-0`}>
                    {d.mandatory ? "Mandatory" : "Optional"}
                  </span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
