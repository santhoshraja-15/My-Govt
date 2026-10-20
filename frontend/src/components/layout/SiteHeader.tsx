"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AuthNav } from "@/components/layout/AuthNav";
import { LangToggle } from "@/components/layout/LangToggle";
import { Database } from "lucide-react";
import { useLang } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";

const ITEMS = [
  { href: "/schemes", key: "nav.schemes" },
  { href: "/services", key: "nav.services" },
  { href: "/complaints", key: "nav.complaints" },
  { href: "/assistant", key: "nav.assistant" },
  { href: "/documents", key: "nav.documents" },
] as const;

/** Compact global header for all pages except the landing page (which has its own hero navigation). */
export function SiteHeader() {
  const path = usePathname();
  const { t } = useLang();
  const { user, isStaff, isAdmin } = useAuth();
  if (path === "/") return null;
  const items = [
    ...(user?.role === "citizen" ? [{ href: "/dashboard", label: t("nav.dashboard") }] : []),
    ...ITEMS.map((i) => ({ href: i.href, label: t(i.key) })),
    ...(isStaff ? [{ href: "/officer", label: t("nav.officer") }] : []),
    ...(isAdmin ? [{ href: "/admin", label: t("nav.admin") }, { href: "/database-architecture", label: t("nav.architecture"), icon: true }] : []),
  ];
  return (
    <header className="bg-brand-800 text-white" data-testid="site-header">
      <div className="max-w-6xl mx-auto px-4 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-2">
        <Link href="/" className="font-black tracking-tight">MyGovt</Link>
        <nav aria-label={t("nav.main")} className="flex flex-wrap gap-4 text-sm text-blue-100">
          {items.map((i) => (
            <Link key={i.href} href={i.href} aria-current={path.startsWith(i.href) ? "page" : undefined}
              data-testid={i.href === "/database-architecture" ? "nav-database-architecture" : undefined}
              className={`${path.startsWith(i.href) ? "text-white font-semibold underline underline-offset-4" : "hover:text-white"} ${i.icon ? "inline-flex items-center gap-1.5 rounded-lg bg-white/10 px-2.5 py-1 hover:bg-white/20" : ""}`}>
              {i.icon && <Database size={14} aria-hidden />}{i.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3"><LangToggle /><AuthNav /></div>
      </div>
    </header>
  );
}
