"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { homeFor, useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";

/** Sign in / Register links, or the signed-in user's name with a sign-out button. */
export function AuthNav({ className = "" }: { className?: string }) {
  const { user, loading, logout } = useAuth();
  const { t } = useLang();
  const path = usePathname();
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
      {path === "/" && <Link href={homeFor(user.role)} data-testid="home-link" className="text-sm underline">{user.role === "citizen" ? t("nav.myDashboard") : user.role === "officer" || user.role === "department_admin" ? t("nav.console") : t("nav.admin")}</Link>}
      <span data-testid="user-name" className="text-sm font-medium">{user.full_name || user.email}</span>
      <button onClick={() => logout()} className="btn-ghost text-blue-100 hover:bg-white/10 hover:text-white">{t("auth.logout")}</button>
    </span>
  );
}
