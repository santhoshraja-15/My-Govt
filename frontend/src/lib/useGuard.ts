"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { homeFor, useAuth, type AuthUser } from "@/lib/auth";

/**
 * Page guard: sends signed-out visitors to /login (and back afterwards) and sends users of the wrong role to their own
 * home page. Returns the user once the page may render, otherwise null. The API enforces the same rules server-side.
 */
export function useGuard(allowed: (role: string) => boolean): AuthUser | null {
  const { user, loading } = useAuth();
  const router = useRouter();
  const path = usePathname();
  const ok = !!user && allowed(user.role);
  useEffect(() => {
    if (loading) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(path)}`);
    else if (!allowed(user.role)) router.replace(homeFor(user.role));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, user, path, router]);
  return ok ? user : null;
}
