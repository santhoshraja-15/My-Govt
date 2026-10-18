"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";

function Inner({ mode }: { mode: "login" | "register" }) {
  const { login, register } = useAuth();
  const { t } = useLang();
  const router = useRouter();
  const next = useSearchParams().get("next") || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") {
        const u = await login(email.trim(), password);
        router.push(next.startsWith("/") ? next : "/");
        void u;
      } else {
        await register(email.trim(), password, name.trim());
        router.push(next.startsWith("/") ? next : "/");
      }
    } catch (err: any) {
      setError(err.status === 401 ? "Invalid email or password." : err.status === 429 ? "Too many attempts. Please wait and try again." : err.message || t("common.error"));
    }
    setBusy(false);
  };

  return (
    <main className="max-w-md mx-auto px-4 py-12">
      <form onSubmit={submit} className="card p-6 space-y-4" aria-labelledby="auth-title">
        <h1 id="auth-title" className="text-xl font-bold text-slate-900">
          {mode === "login" ? t("auth.signin.title") : t("auth.register.title")}
        </h1>
        {error && <div role="alert" className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700">{error}</div>}
        {mode === "register" && (
          <div>
            <label htmlFor="full_name" className="label">{t("auth.fullname")}</label>
            <input id="full_name" className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} autoComplete="name" />
          </div>
        )}
        <div>
          <label htmlFor="email" className="label">{t("auth.email")}</label>
          <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </div>
        <div>
          <label htmlFor="password" className="label">{t("auth.password")}</label>
          <input id="password" type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)}
            required minLength={mode === "register" ? 8 : undefined} autoComplete={mode === "login" ? "current-password" : "new-password"} />
          {mode === "register" && <p className="text-xs text-slate-500 mt-1">At least 8 characters.</p>}
        </div>
        <button type="submit" disabled={busy} className="btn-primary w-full justify-center">
          {busy ? <Loader2 size={16} className="animate-spin" /> : mode === "login" ? t("auth.signin") : t("auth.register")}
        </button>
        <p className="text-sm text-slate-500 text-center">
          {mode === "login"
            ? <>No account? <Link href="/register" className="text-brand-700 underline">{t("auth.register")}</Link></>
            : <>Already registered? <Link href="/login" className="text-brand-700 underline">{t("auth.signin")}</Link></>}
        </p>
      </form>
    </main>
  );
}

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  return <Suspense fallback={null}><Inner mode={mode} /></Suspense>;
}
