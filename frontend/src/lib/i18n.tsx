"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { common } from "@/lib/locales/common";
import { catalog } from "@/lib/locales/catalog";
import { home } from "@/lib/locales/home";
import { auth } from "@/lib/locales/auth";
import { dashboard } from "@/lib/locales/dashboard";
import { complaints } from "@/lib/locales/complaints";
import { assistant } from "@/lib/locales/assistant";
import { officer } from "@/lib/locales/officer";
import { admin } from "@/lib/locales/admin";
import { architecture } from "@/lib/locales/architecture";

export type Lang = "en" | "ta";

/**
 * Every UI string lives in a locale module under lib/locales as `{ en, ta }`. Each module types `ta` as
 * Record<keyof typeof en, string>, so a missing Tamil entry is a compile error rather than a silent English fallback.
 * The Tamil text is an unreviewed translation written for this project - it has NOT been checked by a professional translator.
 * Government-supplied Tamil names (name_ta fields in the database) are shown through `names()` / `<BilingualName>`.
 */
const MODULES = [common, catalog, home, auth, dashboard, complaints, assistant, officer, admin, architecture];
const EN: Record<string, string> = Object.assign({}, ...MODULES.map((m) => m.en));
const TA: Record<string, string> = Object.assign({}, ...MODULES.map((m) => m.ta));

type KeysOf<M extends { en: object }> = keyof M["en"];
export type TKey = KeysOf<typeof common> | KeysOf<typeof catalog> | KeysOf<typeof home> | KeysOf<typeof auth> | KeysOf<typeof dashboard>
  | KeysOf<typeof complaints> | KeysOf<typeof assistant> | KeysOf<typeof officer> | KeysOf<typeof admin> | KeysOf<typeof architecture>;
export type Vars = Record<string, string | number>;

interface LangState {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Translate a key; `{name}` placeholders are replaced from `vars`. */
  t: (key: TKey, vars?: Vars) => string;
  /** Translate a data code (e.g. category "land_records") through a key prefix; unknown codes fall back to the humanised code. */
  label: (prefix: string, code?: string | null) => string;
  /** Like pick(), but also reports the language of the text actually returned (for the lang attribute). */
  pickL: (en?: string | null, ta?: string | null) => { text: string; lang: Lang };
  /** Prefer the Tamil value when Tamil is selected and present; otherwise fall back to English. For free-text data fields. */
  pick: (en?: string | null, ta?: string | null) => string;
  /** Scheme / service display name: English and Tamil together, selected language first. */
  names: (en?: string | null, ta?: string | null) => { primary: string; secondary: string | null; text: string };
  /** Localised message for a failed API call: chosen from the HTTP status, never from the server's English text. */
  apiError: (e: unknown) => string;
  /** Locale-aware date (ISO yyyy-mm-dd or timestamp). */
  fmtDate: (iso?: string | null) => string;
  fmtNumber: (n: number) => string;
}

const Ctx = createContext<LangState | null>(null);

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    try {
      const saved = localStorage.getItem("lang");
      if (saved === "ta" || saved === "en") setLangState(saved);
    } catch { /* storage unavailable */ }
  }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem("lang", l); } catch { /* ignore */ }
  }, []);

  const t = useCallback((key: TKey, vars?: Vars) => {
    const dict = lang === "ta" ? TA : EN;
    let s = dict[key as string];
    if (s === undefined) {
      if (typeof console !== "undefined") console.warn(`[i18n] missing ${lang} translation for "${key}"`);
      s = EN[key as string] ?? (key as string);
    }
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
    return s;
  }, [lang]);

  const label = useCallback((prefix: string, code?: string | null) => {
    if (!code) return "";
    const key = `${prefix}.${code}`;
    const dict = lang === "ta" ? TA : EN;
    if (dict[key] !== undefined) return dict[key];
    return code.replace(/_/g, " ");
  }, [lang]);

  const pick = useCallback((en?: string | null, ta?: string | null) => (lang === "ta" && ta ? ta : en ?? ta ?? ""), [lang]);

  const pickL = useCallback((en?: string | null, ta?: string | null) => (lang === "ta" && ta ? { text: ta, lang: "ta" as Lang } : { text: en ?? ta ?? "", lang: (en ? "en" : ta ? "ta" : "en") as Lang }), [lang]);

  const names = useCallback((en?: string | null, ta?: string | null) => {
    const a = en ?? "", b = ta ?? "";
    const primary = lang === "ta" ? (b || a) : (a || b);
    const secondary = lang === "ta" ? (b && a ? a : null) : (a && b ? b : null);
    return { primary, secondary, text: secondary ? `${primary} (${secondary})` : primary };
  }, [lang]);

  const apiError = useCallback((e: unknown) => {
    const status = (e as { status?: number } | null)?.status;
    const code = (e as { code?: string } | null)?.code;
    if (code === "NETWORK_ERROR" || status === 0) return t("err.network");
    if (status === 401) return t("err.unauthorized");
    if (status === 403) return t("err.forbidden");
    if (status === 404) return t("err.notFound");
    if (status === 422 || status === 400) return t("err.validation");
    if (status === 429) return t("err.rateLimited");
    if (status && status >= 500) return t("err.server");
    return t("err.generic");
  }, [t]);

  const fmtDate = useCallback((iso?: string | null) => {
    if (!iso) return "";
    const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(lang === "ta" ? "ta-IN" : "en-IN", { day: "numeric", month: "short", year: "numeric" });
  }, [lang]);
  const fmtNumber = useCallback((n: number) => n.toLocaleString(lang === "ta" ? "ta-IN" : "en-IN"), [lang]);

  const value = useMemo(() => ({ lang, setLang, t, label, pick, pickL, names, apiError, fmtDate, fmtNumber }), [lang, setLang, t, label, pick, pickL, names, apiError, fmtDate, fmtNumber]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLang(): LangState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLang must be used inside <LangProvider>");
  return v;
}

/** Test hook: every key present in English must exist in Tamil (also enforced by the TypeScript types). */
export const __dictionaries = { EN, TA };
