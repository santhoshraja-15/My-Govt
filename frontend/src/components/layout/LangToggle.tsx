"use client";

import { useLang } from "@/lib/i18n";

/** English / தமிழ் switch. */
export function LangToggle({ className = "" }: { className?: string }) {
  const { lang, setLang } = useLang();
  return (
    <div role="group" aria-label="Language" className={`inline-flex rounded-lg overflow-hidden border border-white/30 text-xs ${className}`}>
      {(["en", "ta"] as const).map((l) => (
        <button key={l} type="button" onClick={() => setLang(l)} aria-pressed={lang === l} lang={l}
          className={`px-2.5 py-1 ${lang === l ? "bg-white text-brand-700 font-bold" : "text-blue-100 hover:bg-white/10"}`}>
          {l === "en" ? "EN" : "தமிழ்"}
        </button>
      ))}
    </div>
  );
}
