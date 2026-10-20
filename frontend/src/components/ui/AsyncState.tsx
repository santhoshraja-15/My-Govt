"use client";

import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { useLang } from "@/lib/i18n";

/** Consistent loading / error / empty presentation for data-driven lists. */
export function LoadingState({ label }: { label?: string }) {
  const { t } = useLang();
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-2 py-12 text-slate-500">
      <Loader2 size={18} className="animate-spin" /> {label ?? t("common.loading")}
    </div>
  );
}

export function ErrorState({ message, onRetry, retryLabel }: { message: string; onRetry?: () => void; retryLabel?: string }) {
  const { t } = useLang();
  return (
    <div role="alert" className="flex flex-col items-center gap-3 py-12 text-red-700">
      <span className="flex items-center gap-2"><AlertTriangle size={18} /> {message}</span>
      {onRetry && <button type="button" onClick={onRetry} className="btn-secondary">{retryLabel ?? t("common.retry")}</button>}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-slate-500" data-testid="empty-state">
      <Inbox size={22} /> {message}
    </div>
  );
}
