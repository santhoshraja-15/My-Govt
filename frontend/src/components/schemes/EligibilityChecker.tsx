"use client";

import { useId, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";

type Field =
  | { key: string; label: string; kind: "number"; min: number; max: number; step?: number; hint?: string }
  | { key: string; label: string; kind: "select"; options: [string, string][]; hint?: string }
  | { key: string; label: string; kind: "text"; maxLength: number; hint?: string };

const YES_NO: [string, string][] = [["", "Not specified"], ["true", "Yes"], ["false", "No"]];
const FIELDS: Field[] = [
  { key: "age", label: "Age (years)", kind: "number", min: 0, max: 120 },
  { key: "gender", label: "Gender", kind: "select", options: [["", "Not specified"], ["female", "Female"], ["male", "Male"], ["transgender", "Transgender"], ["other", "Other"]] },
  { key: "annual_income", label: "Annual family income (₹)", kind: "number", min: 0, max: 1_000_000_000, step: 1000, hint: "Total yearly income of the family; leave empty if unknown." },
  { key: "social_category", label: "Social category", kind: "select", options: [["", "Not specified"], ["OC", "OC"], ["BC", "BC"], ["MBC", "MBC"], ["SC", "SC"], ["ST", "ST"]] },
  { key: "bpl_status", label: "Below poverty line (BPL) household?", kind: "select", options: YES_NO },
  { key: "disability_status", label: "Person with a disability?", kind: "select", options: YES_NO },
  { key: "is_student", label: "Currently a student?", kind: "select", options: YES_NO },
  { key: "occupation", label: "Occupation", kind: "text", maxLength: 80, hint: "For example: farmer, student, daily wage worker." },
  { key: "education_level", label: "Highest education", kind: "select", options: [["", "Not specified"], ["below_10th", "Below 10th"], ["10th", "10th"], ["12th", "12th"], ["graduate", "Graduate"], ["postgraduate", "Postgraduate"]] },
];

const TONE = {
  ELIGIBLE: { box: "bg-emerald-50 border-emerald-300", title: "text-emerald-800", icon: <CheckCircle2 size={34} className="text-emerald-600 mx-auto mb-2" aria-hidden />, text: "You appear to meet the recorded criteria" },
  NOT_ELIGIBLE: { box: "bg-red-50 border-red-300", title: "text-red-800", icon: <XCircle size={34} className="text-red-600 mx-auto mb-2" aria-hidden />, text: "You do not meet the recorded criteria" },
  INSUFFICIENT_DATA: { box: "bg-amber-50 border-amber-300", title: "text-amber-900", icon: <AlertCircle size={34} className="text-amber-700 mx-auto mb-2" aria-hidden />, text: "Not enough information to decide" },
} as const;
const OUTCOME_CLASS: Record<string, string> = { PASS: "badge-green", FAIL: "badge-red", UNKNOWN: "badge-yellow" };
const OUTCOME_TEXT: Record<string, string> = { PASS: "Meets", FAIL: "Does not meet", UNKNOWN: "Unknown" };

/**
 * Indicative eligibility check against the rules RECORDED for the scheme. Blank answers stay "unknown" (never guessed).
 * The result is not an application and not an approval; the department decides.
 */
export function EligibilityChecker({ scheme, onResult }: { scheme: any; onResult?: (r: any | null) => void }) {
  const uid = useId();
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<any>(null);
  const [serverError, setServerError] = useState("");
  const [busy, setBusy] = useState(false);
  const rules: any[] = scheme.eligibility_rules ?? [];
  const demo = rules.some((r) => String(r.source_reference || "").startsWith("DEMO RULE"));
  const ruleById = Object.fromEntries(rules.map((r) => [r.rule_id, r]));

  const validate = () => {
    const e: Record<string, string> = {};
    for (const f of FIELDS) {
      const v = (values[f.key] ?? "").trim();
      if (f.kind === "number" && v !== "") {
        const n = Number(v);
        if (!Number.isFinite(n)) e[f.key] = "Enter a number.";
        else if (n < f.min || n > f.max) e[f.key] = `Enter a value between ${f.min.toLocaleString("en-IN")} and ${f.max.toLocaleString("en-IN")}.`;
        else if (f.key === "age" && !Number.isInteger(n)) e[f.key] = "Enter whole years.";
      }
      if (f.kind === "text" && v.length > f.maxLength) e[f.key] = `At most ${f.maxLength} characters.`;
    }
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setServerError("");
    if (!validate()) return;
    const payload: Record<string, any> = {};
    for (const f of FIELDS) {
      const v = (values[f.key] ?? "").trim();
      if (v === "") continue;
      payload[f.key] = f.kind === "number" ? Number(v) : v === "true" ? true : v === "false" ? false : v;
    }
    setBusy(true);
    try {
      const r = await schemesAPI.checkEligibility(scheme.scheme_id, payload);
      setResult(r);
      onResult?.(r);
    } catch (e: any) {
      setServerError(e?.message || "The check could not be completed. Please try again.");
    }
    setBusy(false);
  };
  const reset = () => { setResult(null); setErrors({}); setServerError(""); onResult?.(null); };
  const clearAll = () => { setValues({}); reset(); };

  if (rules.length === 0) {
    return (
      <section className="card p-5 text-sm text-slate-700" data-testid="eligibility-no-rules" aria-label="Eligibility check">
        <h3 className="font-bold text-slate-900 mb-1">Check my eligibility</h3>
        No eligibility rules have been recorded for this scheme yet, so the platform cannot evaluate your answers. Please contact the
        department for the official conditions.
      </section>
    );
  }

  const tone = result ? (TONE as any)[result.overall] ?? TONE.INSUFFICIENT_DATA : null;
  return (
    <section className="card p-5 space-y-4" aria-label="Eligibility check" data-testid="eligibility-checker">
      <div>
        <h3 className="font-bold text-slate-900 text-lg">Check my eligibility</h3>
        <p className="text-sm text-slate-600">
          Answer only what you know — anything left blank is treated as unknown, never guessed. This is an <b>indicative</b> check against the criteria
          recorded here; it is not an application and not an approval.
        </p>
        {demo && <p className="mt-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900" data-testid="checker-demo-note">
          These criteria are demonstration rules, not the scheme&apos;s official conditions.</p>}
      </div>

      {!result ? (
        <form onSubmit={submit} noValidate className="space-y-4" data-testid="eligibility-form">
          <div className="grid sm:grid-cols-2 gap-4">
            {FIELDS.map((f) => {
              const id = `${uid}-${f.key}`;
              const err = errors[f.key];
              const common = { id, "aria-invalid": !!err, "aria-describedby": err ? `${id}-err` : f.hint ? `${id}-hint` : undefined, "data-testid": `field-${f.key}` } as const;
              return (
                <div key={f.key}>
                  <label htmlFor={id} className="label">{f.label} <span className="text-slate-500 font-normal">(optional)</span></label>
                  {f.kind === "select" ? (
                    <select {...common} className="input" value={values[f.key] ?? ""} onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))}>
                      {f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  ) : f.kind === "number" ? (
                    <input {...common} className="input" type="number" inputMode="decimal" min={f.min} max={f.max} step={f.step ?? 1} value={values[f.key] ?? ""}
                      onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))} />
                  ) : (
                    <input {...common} className="input" type="text" maxLength={f.maxLength + 20} value={values[f.key] ?? ""}
                      onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))} />
                  )}
                  {f.hint && !err && <p id={`${id}-hint`} className="text-xs text-slate-500 mt-1">{f.hint}</p>}
                  {err && <p id={`${id}-err`} role="alert" className="text-xs text-red-700 mt-1" data-testid={`error-${f.key}`}>{err}</p>}
                </div>
              );
            })}
          </div>
          {serverError && <p role="alert" className="rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700" data-testid="checker-error">{serverError}</p>}
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy} className="btn-primary" data-testid="check-eligibility">
              {busy ? <><Loader2 size={16} className="animate-spin" aria-hidden /> Checking…</> : "Check eligibility"}
            </button>
            <button type="button" className="btn-ghost" onClick={clearAll} data-testid="clear-answers">Clear answers</button>
          </div>
        </form>
      ) : (
        <div className="space-y-4" aria-live="polite" data-testid="eligibility-result" data-overall={result.overall}>
          <div className={`rounded-2xl border-2 p-5 text-center ${tone.box}`}>
            {tone.icon}
            <h4 className={`font-bold text-lg ${tone.title}`} data-testid="eligibility-headline">{tone.text}</h4>
            <p className="text-xs text-slate-700 mt-1">{result.disclaimer || "Indicative only. The department decides; this is not an approval."}</p>
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-100">
            <table className="data-table text-xs" data-testid="rule-results">
              <thead><tr><th>Criterion</th><th>Your answer</th><th>Result</th></tr></thead>
              <tbody>
                {result.rule_results.map((r: any) => (
                  <tr key={r.rule_id} data-outcome={r.outcome}>
                    <td>{ruleById[r.rule_id]?.human_readable ?? `${r.attribute} ${r.operator} ${JSON.stringify(r.threshold)}`}{r.mandatory ? "" : " (optional)"}</td>
                    <td>{r.citizen_value === null || r.citizen_value === undefined ? <span className="text-slate-500">not given</span> : String(r.citizen_value)}</td>
                    <td><span className={`badge ${OUTCOME_CLASS[r.outcome] ?? "badge-slate"}`}>{OUTCOME_TEXT[r.outcome] ?? r.outcome}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.missing_attributes?.length > 0 && (
            <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900" data-testid="missing-info">
              Information that would help: <b>{result.missing_attributes.join(", ")}</b>.
            </p>
          )}
          <button type="button" className="btn-secondary" onClick={reset} data-testid="recheck">Change my answers</button>
        </div>
      )}
    </section>
  );
}
