/**
 * Shows how far a record has been verified. Only `official_verified` may be presented as
 * verified; everything else is labelled so citizens can tell it apart.
 */
const STYLES: Record<string, { label: string; cls: string; title: string }> = {
  official_verified: {
    label: "Verified",
    cls: "badge-green",
    title: "Verified against an official source document",
  },
  externally_referenced: {
    label: "External source",
    cls: "badge-yellow",
    title: "Referenced from a non-state source; not verified against a Tamil Nadu official document",
  },
  provisional: {
    label: "Provisional",
    cls: "badge-yellow",
    title: "Not yet verified against an official document. Confirm with the department before acting.",
  },
  unverified: { label: "Unverified", cls: "badge-slate", title: "Unverified" },
  deprecated: { label: "Deprecated", cls: "badge-slate", title: "No longer current" },
};

export function VerificationBadge({ status }: { status?: string | null }) {
  const s = STYLES[status ?? "unverified"] ?? STYLES.unverified;
  return (
    <span className={`badge ${s.cls}`} title={s.title} data-testid="verification-badge" data-status={status ?? "unverified"}>
      {s.label}
    </span>
  );
}

export default VerificationBadge;
