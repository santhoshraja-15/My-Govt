"use client";

import { useLang, type TKey } from "@/lib/i18n";

/**
 * Shows how far a record has been verified. Only `official_verified` may be presented as
 * verified; everything else is labelled so citizens can tell it apart.
 */
const STYLES: Record<string, { label: TKey; cls: string; title: TKey }> = {
  official_verified: { label: "status.verified", cls: "badge-green", title: "status.verified.title" },
  externally_referenced: { label: "status.external", cls: "badge-yellow", title: "status.external.title" },
  provisional: { label: "status.provisional", cls: "badge-yellow", title: "status.provisional.title" },
  unverified: { label: "status.unverified", cls: "badge-slate", title: "status.unverified.title" },
  deprecated: { label: "status.deprecated", cls: "badge-slate", title: "status.deprecated.title" },
};

export function VerificationBadge({ status }: { status?: string | null }) {
  const { t } = useLang();
  const s = STYLES[status ?? "unverified"] ?? STYLES.unverified;
  return (
    <span className={`badge ${s.cls}`} title={t(s.title)} data-testid="verification-badge" data-status={status ?? "unverified"}>
      {t(s.label)}
    </span>
  );
}

export default VerificationBadge;
