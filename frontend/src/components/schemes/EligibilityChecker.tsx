"use client";

import { useId, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { schemes as schemesAPI } from "@/lib/api";
import { useLang, type TKey } from "@/lib/i18n";

type Field =
  | { key: string; kind: "number"; min: number; max: number; step?: number; hint?: boolean }
  | { key: string; kind: "select"; options: [string, string][]; hint?: boolean }
  | { key: string; kind: "text"; maxLength: number; hint?: boolean };

// Option labels are translation keys (elig.*); "" is the 'not specified' option.
const YES_NO: [string, string][] = [["", "elig.notSpecified"], ["true", "elig.yes"], ["false", "elig.no"]];
const FIELDS: Field[] = [
  { key: "age", kind: "number", min: 0, max: 120 },
  { key: "gender", kind: "select", options: [["", "elig.notSpecified"], ["female", "elig.g.female"], ["male", "elig.g.male"], ["transgender", "elig.g.transgender"], ["other", "elig.g.other"]] },
  { key: "annual_income", kind: "number", min: 0, max: 1_000_000_000, step: 1000, hint: true },
  { key: "social_category", kind: "select", options: [["", "elig.notSpecified"], ["OC", ""], ["BC", ""], ["MBC", ""], ["SC", ""], ["ST", ""]] },
  { key: "bpl_status", kind: "select", options: YES_NO },
  { key: "disability_status", kind: "select", options: YES_NO },
  { key: "is_student", kind: "select", options: YES_NO },
  { key: "occupation", kind: "text", maxLength: 80, hint: true },
  { key: "education_level", kind: "select", options: [["", "elig.notSpecified"], ["below_10th", "elig.edu.below_10th"], ["10th", "elig.edu.10th"], ["12th", "elig.edu.12th"], ["graduate", "elig.edu.graduate"], ["postgraduate", "elig.edu.postgraduate"]] },
];

const TONE = {
  ELIGIBLE: { box: "bg-emerald-50 border-emerald-300", title: "text-emerald-800", icon: <CheckCircle2 size={34} className="text-emerald-600 mx-auto mb-2" aria-hidden />, key: "elig.headline.ELIGIBLE" as TKey },
  NOT_ELIGIBLE: { box: "bg-red-50 border-red-300", title: "text-red-800", icon: <XCircle size={34} className="text-red-600 mx-auto mb-2" aria-hidden />, key: "elig.headline.NOT_ELIGIBLE" as TKey },
  INSUFFICIENT_DATA: { box: "bg-amber-50 border-amber-300", title: "text-amber-900", icon: <AlertCircle size={34} className="text-amber-700 mx-auto mb-2" aria-hidden />, key: "elig.headline.INSUFFICIENT_DATA" as TKey },
} as const;
const OUTCOME_CLASS: Record<string, string> = { PASS: "badge-green", FAIL: "badge-red", UNKNOWN: "badge-yellow" };

/**
 * Indicative eligibility check against the rules RECORDED for the scheme. Blank answers stay "unknown" (never guessed).
 * The result is not an application and not an approval; the department decides.
 */
export function EligibilityChecker({ scheme, onResult }: { scheme: any; onResult?: (r: any | null) => void }) {
  const uid = useId();
  const { t, pickL, fmtNumber } = useLang();
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
        if (!Number.isFinite(n)) e[f.key] = t("elig.err.number");
        else if (n < f.min || n > f.max) e[f.key] = t("elig.err.range", { min: fmtNumber(f.min), max: fmtNumber(f.max) });
        else if (f.key === "age" && !Number.isInteger(n)) e[f.key] = t("elig.err.wholeYears");
      }
      if (f.kind === "text" && v.length > f.maxLength) e[f.key] = t("elig.err.maxChars", { max: f.maxLength });
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
      setServerError(t("elig.err.server"));
    }
    setBusy(false);
  };
  const reset = () => { setResult(null); setErrors({}); setServerError(""); onResult?.(null); };
  const clearAll = () => { setValues({}); reset(); };

  if (rules.length === 0) {
    return (
      <section className="card p-5 text-sm text-slate-700" data-testid="eligibility-no-rules" aria-label={t("elig.title")}>
        <h3 className="font-bold text-slate-900 mb-1">{t("elig.title")}</h3>
        {t("elig.noRules")}
      </section>
    );
  }

  const tone = result ? (TONE as any)[result.overall] ?? TONE.INSUFFICIENT_DATA : null;
  return (
    <section className="card p-5 space-y-4" aria-label={t("elig.title")} data-testid="eligibility-checker">
      <div>
        <h3 className="font-bold text-slate-900 text-lg">{t("elig.title")}</h3>
        <p className="text-sm text-slate-600">
          {t("elig.intro")}
        </p>
        {demo && <p className="mt-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900" data-testid="checker-demo-note">
          {t("elig.demoNote")}</p>}
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
                  <label htmlFor={id} className="label">{t(`elig.f.${f.key}` as TKey)} <span className="text-slate-500 font-normal">{t("elig.optional")}</span></label>
                  {f.kind === "select" ? (
                    <select {...common} className="input" value={values[f.key] ?? ""} onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))}>
                      {f.options.map(([v, l]) => <option key={v} value={v}>{l ? t(l as TKey) : v}</option>)}
                    </select>
                  ) : f.kind === "number" ? (
                    <input {...common} className="input" type="number" inputMode="decimal" min={f.min} max={f.max} step={f.step ?? 1} value={values[f.key] ?? ""}
                      onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))} />
                  ) : (
                    <input {...common} className="input" type="text" maxLength={f.maxLength + 20} value={values[f.key] ?? ""}
                      onChange={(e) => setValues((p) => ({ ...p, [f.key]: e.target.value }))} />
                  )}
                  {f.hint && !err && <p id={`${id}-hint`} className="text-xs text-slate-500 mt-1">{t(`elig.hint.${f.key}` as TKey)}</p>}
                  {err && <p id={`${id}-err`} role="alert" className="text-xs text-red-700 mt-1" data-testid={`error-${f.key}`}>{err}</p>}
                </div>
              );
            })}
          </div>
          {serverError && <p role="alert" className="rounded-xl bg-red-50 border border-red-200 p-3 text-sm text-red-700" data-testid="checker-error">{serverError}</p>}
          <div className="flex flex-wrap gap-3">
            <button type="submit" disabled={busy} className="btn-primary" data-testid="check-eligibility">
              {busy ? <><Loader2 size={16} className="animate-spin" aria-hidden /> {t("elig.checking")}</> : t("elig.check")}
            </button>
            <button type="button" className="btn-ghost" onClick={clearAll} data-testid="clear-answers">{t("elig.clear")}</button>
          </div>
        </form>
      ) : (
        <div className="space-y-4" aria-live="polite" data-testid="eligibility-result" data-overall={result.overall}>
          <div className={`rounded-2xl border-2 p-5 text-center ${tone.box}`}>
            {tone.icon}
            <h4 className={`font-bold text-lg ${tone.title}`} data-testid="eligibility-headline">{t(tone.key)}</h4>
            <p className="text-xs text-slate-700 mt-1">{t("elig.disclaimer")}</p>
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-100">
            <table className="data-table text-xs" data-testid="rule-results">
              <thead><tr><th>{t("elig.col.criterion")}</th><th>{t("elig.col.answer")}</th><th>{t("elig.col.result")}</th></tr></thead>
              <tbody>
                {result.rule_results.map((r: any) => (
                  <tr key={r.rule_id} data-outcome={r.outcome}>
                    <td>{ruleById[r.rule_id] ? <span lang={pickL(ruleById[r.rule_id].human_readable, ruleById[r.rule_id].human_readable_ta).lang}>{pickL(ruleById[r.rule_id].human_readable, ruleById[r.rule_id].human_readable_ta).text}</span> : `${r.attribute} ${r.operator} ${JSON.stringify(r.threshold)}`}{r.mandatory ? "" : ` ${t("elig.optional")}`}</td>
                    <td>{r.citizen_value === null || r.citizen_value === undefined ? <span className="text-slate-500">{t("elig.notGiven")}</span> : String(r.citizen_value)}</td>
                    <td><span className={`badge ${OUTCOME_CLASS[r.outcome] ?? "badge-slate"}`}>{t(`elig.out.${r.outcome}` as TKey)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.missing_attributes?.length > 0 && (
            <p className="rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900" data-testid="missing-info">
              {t("elig.missing")} <b>{result.missing_attributes.map((a: string) => t(`elig.attr.${a}` as TKey)).join(", ")}</b>.
            </p>
          )}
          <button type="button" className="btn-secondary" onClick={reset} data-testid="recheck">{t("elig.change")}</button>
        </div>
      )}
    </section>
  );
}
