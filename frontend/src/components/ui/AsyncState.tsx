import { AlertTriangle, Inbox, Loader2 } from "lucide-react";

/** Consistent loading / error / empty presentation for data-driven lists. */
export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-2 py-12 text-slate-500">
      <Loader2 size={18} className="animate-spin" /> {label}
    </div>
  );
}

export function ErrorState({ message, onRetry, retryLabel = "Try again" }: { message: string; onRetry?: () => void; retryLabel?: string }) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 py-12 text-red-700">
      <span className="flex items-center gap-2"><AlertTriangle size={18} /> {message}</span>
      {onRetry && <button type="button" onClick={onRetry} className="btn-secondary">{retryLabel}</button>}
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
