"use client";

import Link from "next/link";
import { Compass } from "lucide-react";
import { useLang } from "@/lib/i18n";

export default function NotFound() {
  const { t } = useLang();
  return (
    <main className="max-w-xl mx-auto px-4 py-24 text-center space-y-4" data-testid="not-found">
      <Compass size={48} className="mx-auto text-slate-500" aria-hidden />
      <h1 className="text-3xl font-black text-slate-900">{t("nf.title")}</h1>
      <p className="text-slate-600">{t("nf.text")}</p>
      <div className="flex justify-center gap-3">
        <Link href="/" className="btn-primary">{t("nf.home")}</Link>
        <Link href="/schemes" className="btn-secondary">{t("nf.schemes")}</Link>
      </div>
    </main>
  );
}
