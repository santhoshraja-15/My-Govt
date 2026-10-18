"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, XCircle, AlertCircle, ExternalLink, Award, FileText, Shield, Loader2 } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";
import { use } from "react";

function RuleBadge({ outcome }: { outcome: string }) {
  if (outcome === "PASS") return <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />;
  if (outcome === "FAIL") return <XCircle size={14} className="text-red-500 shrink-0" />;
  return <AlertCircle size={14} className="text-amber-400 shrink-0" />;
}

export default function SchemeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [scheme, setScheme] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "eligibility" | "documents" | "benefits">("overview");

  useEffect(() => {
    schemesAPI.get(id).then(setScheme).catch(() => setScheme(null)).finally(() => setLoading(false));
  }, [id]);

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
            {scheme.department_name && <span className="badge badge-blue">{scheme.department_name}</span>}
            {scheme.category && <span className="badge badge-slate capitalize">{scheme.category.replace(/_/g," ")}</span>}
            <span className="badge badge-green capitalize">{scheme.scheme_level}</span>
            {scheme.verified_at && (
              <span className="badge badge-purple flex items-center gap-1">
                <CheckCircle2 size={10} /> Verified
              </span>
            )}
          </div>
          <h1 className="text-2xl md:text-3xl font-black mb-2">{scheme.name}</h1>
          {scheme.name_ta && <p className="text-blue-300 font-tamil text-lg">{scheme.name_ta}</p>}
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Tabs */}
        <div className="flex gap-1 bg-white rounded-xl p-1 border border-slate-200 mb-6 overflow-x-auto">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key as any)}
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
            </div>

            {(scheme.application_url || scheme.official_source_url) && (
              <div className="card p-5 flex flex-wrap gap-3">
                {scheme.application_url && (
                  <a href={scheme.application_url} target="_blank" rel="noopener noreferrer" className="btn-primary">
                    Apply Online <ExternalLink size={14} />
                  </a>
                )}
                {scheme.official_source_url && (
                  <a href={scheme.official_source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary">
                    Official Source <ExternalLink size={14} />
                  </a>
                )}
              </div>
            )}
          </div>
        )}

        {tab === "eligibility" && (
          <div className="space-y-4 animate-fade-in">
            {!scheme.eligibility_rules?.length ? (
              <div className="card p-8 text-center text-slate-400">
                <Shield size={36} className="mx-auto mb-2 opacity-40" />
                <p>No eligibility rules defined for this scheme yet.</p>
              </div>
            ) : (
              <>
                <div className="card p-4 bg-blue-50 border-blue-100 text-sm text-blue-700">
                  These are the official eligibility criteria. Rules in the same group (AND logic) must all pass.
                </div>
                {Object.entries(
                  scheme.eligibility_rules.reduce((acc: any, rule: any) => {
                    const g = rule.rule_group || 1;
                    acc[g] = acc[g] || [];
                    acc[g].push(rule);
                    return acc;
                  }, {})
                ).map(([group, rules]: any) => (
                  <div key={group} className="card p-5">
                    <p className="text-xs font-semibold text-slate-400 mb-3 uppercase tracking-wide">
                      Criteria Group {group}
                    </p>
                    <div className="space-y-3">
                      {rules.map((rule: any) => (
                        <div key={rule.rule_id} className="flex items-start gap-3 p-3 bg-slate-50 rounded-xl">
                          <RuleBadge outcome="UNKNOWN" />
                          <div className="flex-1">
                            <p className="text-sm font-medium text-slate-800">{rule.human_readable}</p>
                            {rule.human_readable_ta && (
                              <p className="text-xs text-slate-400 font-tamil mt-0.5">{rule.human_readable_ta}</p>
                            )}
                            {rule.source_reference && (
                              <p className="text-xs text-slate-400 mt-1">Source: {rule.source_reference}</p>
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
              <div className="card p-8 text-center text-slate-400">
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
                    <p className="text-xs text-slate-400 uppercase tracking-wide mb-0.5">{b.benefit_type?.replace(/_/g," ")}</p>
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
              <div className="card p-8 text-center text-slate-400">
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
