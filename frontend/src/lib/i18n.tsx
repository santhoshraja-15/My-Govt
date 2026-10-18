"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export type Lang = "en" | "ta";

/**
 * UI strings. Tamil text here has NOT been reviewed by an official translator; government-supplied
 * Tamil names (name_ta fields from the database) are shown via `pick()` and take precedence.
 */
const DICT: Record<string, { en: string; ta: string }> = {
  "nav.home": { en: "Home", ta: "முகப்பு" },
  "nav.schemes": { en: "Schemes", ta: "திட்டங்கள்" },
  "nav.services": { en: "Services", ta: "சேவைகள்" },
  "nav.complaints": { en: "Complaints", ta: "புகார்கள்" },
  "nav.assistant": { en: "AI Assistant", ta: "உதவியாளர்" },
  "nav.documents": { en: "Documents", ta: "ஆவணங்கள்" },
  "auth.signin": { en: "Sign In", ta: "உள்நுழைய" },
  "auth.register": { en: "Register", ta: "பதிவு செய்ய" },
  "auth.logout": { en: "Sign out", ta: "வெளியேறு" },
  "auth.email": { en: "Email", ta: "மின்னஞ்சல்" },
  "auth.password": { en: "Password", ta: "கடவுச்சொல்" },
  "auth.fullname": { en: "Full name", ta: "முழு பெயர்" },
  "auth.signin.title": { en: "Sign in to your account", ta: "உங்கள் கணக்கில் உள்நுழையவும்" },
  "auth.register.title": { en: "Create a citizen account", ta: "குடிமக்கள் கணக்கை உருவாக்கவும்" },
  "auth.required": { en: "Please sign in to continue.", ta: "தொடர உள்நுழையவும்." },
  "common.loading": { en: "Loading…", ta: "ஏற்றுகிறது…" },
  "common.error": { en: "Something went wrong. Please try again.", ta: "ஏதோ தவறு நடந்தது. மீண்டும் முயலவும்." },
  "common.empty": { en: "Nothing found.", ta: "எதுவும் கிடைக்கவில்லை." },
  "common.retry": { en: "Try again", ta: "மீண்டும் முயல்க" },
  "complaint.title": { en: "File a New Complaint", ta: "புதிய புகாரை பதிவு செய்ய" },
  "complaint.subject": { en: "Subject", ta: "தலைப்பு" },
  "complaint.description": { en: "Description", ta: "விளக்கம்" },
  "complaint.category": { en: "Category", ta: "வகை" },
  "complaint.submit": { en: "Submit Complaint", ta: "புகாரை சமர்ப்பிக்க" },
  "complaint.track": { en: "Track Existing Complaint", ta: "புகாரின் நிலையை அறிய" },
  "complaint.mine": { en: "My complaints", ta: "எனது புகார்கள்" },
  "complaint.location.consent": {
    en: "I agree to share this location with the department handling my complaint.",
    ta: "எனது புகாரைக் கையாளும் துறையுடன் இந்த இடத்தைப் பகிர ஒப்புக்கொள்கிறேன்.",
  },
  "status.verified": { en: "Verified", ta: "சரிபார்க்கப்பட்டது" },
  "status.provisional": { en: "Provisional", ta: "தற்காலிகம்" },
  "status.external": { en: "External source", ta: "வெளி ஆதாரம்" },
  "status.unverified": { en: "Unverified", ta: "சரிபார்க்கப்படவில்லை" },
};

interface LangState {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string) => string;
  /** Prefer the Tamil value when Tamil is selected and present; otherwise fall back to English. */
  pick: (en?: string | null, ta?: string | null) => string;
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
  const t = useCallback((key: string) => DICT[key]?.[lang] ?? DICT[key]?.en ?? key, [lang]);
  const pick = useCallback((en?: string | null, ta?: string | null) => (lang === "ta" && ta ? ta : en ?? ta ?? ""), [lang]);

  const value = useMemo(() => ({ lang, setLang, t, pick }), [lang, setLang, t, pick]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useLang(): LangState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useLang must be used inside <LangProvider>");
  return v;
}
