"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";

/** Sign in / Register links, or the signed-in user's name with a sign-out button. */
export function AuthNav({ className = "" }: { className?: string }) {
  const { user, loading, logout, isAdmin } = useAuth();
  const { t } = useLang();
  if (loading) return <span className={className} aria-busy="true" />;
  if (!user) {
    return (
      <span className={`flex items-center gap-2 ${className}`}>
        <Link href="/login" className="btn-ghost text-blue-100 hover:bg-white/10 hover:text-white">{t("auth.signin")}</Link>
        <Link href="/register" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shadow-saffron-500/30">{t("auth.register")}</Link>
      </span>
    );
  }
  return (
    <span className={`flex items-center gap-3 text-blue-100 ${className}`}>
      <span data-testid="user-name" className="text-sm font-medium">{user.full_name || user.email}</span>
      {isAdmin && <Link href="/admin" className="text-sm underline">Admin</Link>}
      <button onClick={() => logout()} className="btn-ghost text-blue-100 hover:bg-white/10 hover:text-white">{t("auth.logout")}</button>
    </span>
  );
}
