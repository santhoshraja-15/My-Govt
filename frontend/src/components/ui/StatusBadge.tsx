import { AlertTriangle, CheckCircle2, Clock, XCircle } from "lucide-react";

export const STATUS_META: Record<string, { label: string; color: string; hex: string; icon: typeof Clock }> = {
  submitted:    { label: "Submitted",       color: "badge-blue",   hex: "#3b82f6", icon: Clock },
  needs_triage: { label: "Awaiting triage", color: "badge-yellow", hex: "#f59e0b", icon: Clock },
  classified:   { label: "Classified",      color: "badge-blue",   hex: "#60a5fa", icon: Clock },
  assigned:     { label: "Assigned",        color: "badge-purple", hex: "#8b5cf6", icon: Clock },
  in_progress:  { label: "In progress",     color: "badge-yellow", hex: "#f97316", icon: Clock },
  resolved:     { label: "Resolved",        color: "badge-green",  hex: "#10b981", icon: CheckCircle2 },
  closed:       { label: "Closed",          color: "badge-slate",  hex: "#64748b", icon: CheckCircle2 },
  escalated:    { label: "Escalated",       color: "badge-red",    hex: "#ef4444", icon: AlertTriangle },
  reopened:     { label: "Reopened",        color: "badge-yellow", hex: "#eab308", icon: Clock },
  rejected:     { label: "Rejected",        color: "badge-red",    hex: "#b91c1c", icon: XCircle },
};

export function StatusBadge({ status }: { status: string }) {
  const m = STATUS_META[status] ?? { label: status, color: "badge-slate", icon: Clock };
  const Icon = m.icon;
  return (
    <span className={`badge ${m.color} gap-1`} data-testid="status-badge" data-status={status}>
      <Icon size={10} aria-hidden /> {m.label}
    </span>
  );
}
