"use client";

import { AlertTriangle, CheckCircle2, Clock, XCircle } from "lucide-react";
import { useLang, type TKey } from "@/lib/i18n";

export const STATUS_META: Record<string, { label: string; key?: TKey; color: string; hex: string; icon: typeof Clock }> = {
  submitted:    { key: "cs.submitted", label: "Submitted",       color: "badge-blue",   hex: "#3b82f6", icon: Clock },
  needs_triage: { key: "cs.needs_triage", label: "Awaiting triage", color: "badge-yellow", hex: "#f59e0b", icon: Clock },
  classified:   { key: "cs.classified", label: "Classified",      color: "badge-blue",   hex: "#60a5fa", icon: Clock },
  assigned:     { key: "cs.assigned", label: "Assigned",        color: "badge-purple", hex: "#8b5cf6", icon: Clock },
  in_progress:  { key: "cs.in_progress", label: "In progress",     color: "badge-yellow", hex: "#f97316", icon: Clock },
  resolved:     { key: "cs.resolved", label: "Resolved",        color: "badge-green",  hex: "#10b981", icon: CheckCircle2 },
  closed:       { key: "cs.closed", label: "Closed",          color: "badge-slate",  hex: "#64748b", icon: CheckCircle2 },
  escalated:    { key: "cs.escalated", label: "Escalated",       color: "badge-red",    hex: "#ef4444", icon: AlertTriangle },
  reopened:     { key: "cs.reopened", label: "Reopened",        color: "badge-yellow", hex: "#eab308", icon: Clock },
  rejected:     { key: "cs.rejected", label: "Rejected",        color: "badge-red",    hex: "#b91c1c", icon: XCircle },
};

export function StatusBadge({ status }: { status: string }) {
  const { t } = useLang();
  const m = STATUS_META[status] ?? { label: status, color: "badge-slate", icon: Clock };
  const Icon = m.icon;
  return (
    <span className={`badge ${m.color} gap-1`} data-testid="status-badge" data-status={status}>
      <Icon size={10} aria-hidden /> {m.key ? t(m.key) : m.label}
    </span>
  );
}
