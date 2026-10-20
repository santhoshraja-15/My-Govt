"use client";

/** Dependency-free SVG/CSS charts. Every chart has a text alternative (table or list) so it is usable without sight. */

import { useLang } from "@/lib/i18n";

export interface Slice { label: string; value: number; color: string }

export function DonutChart({ slices, centerLabel, testId }: { slices: Slice[]; centerLabel?: string; testId?: string }) {
  const { t } = useLang();
  const total = slices.reduce((a, s) => a + s.value, 0);
  const R = 52, C = 2 * Math.PI * R;
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center gap-6" data-testid={testId}>
      <svg viewBox="0 0 140 140" className="w-36 h-36 shrink-0 -rotate-90" role="img"
        aria-label={t("chart.donut", { total, items: slices.map((s) => `${s.label} ${s.value}`).join(", ") })}>
        <circle cx="70" cy="70" r={R} fill="none" stroke="#e2e8f0" strokeWidth="16" />
        {total > 0 && slices.filter((s) => s.value > 0).map((s) => {
          const len = (s.value / total) * C;
          const el = (
            <circle key={s.label} cx="70" cy="70" r={R} fill="none" stroke={s.color} strokeWidth="16"
              strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-offset}
              style={{ transition: "stroke-dasharray 0.8s ease" }} />
          );
          offset += len;
          return el;
        })}
        <g className="rotate-90 origin-center" style={{ transformBox: "fill-box" }}>
          <text x="70" y="68" textAnchor="middle" className="fill-slate-900 text-[22px] font-bold">{total}</text>
          <text x="70" y="86" textAnchor="middle" className="fill-slate-500 text-[9px]">{centerLabel ?? "total"}</text>
        </g>
      </svg>
      <ul className="space-y-1.5 text-sm">
        {slices.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: s.color }} aria-hidden />
            <span className="text-slate-600">{s.label}</span>
            <span className="font-semibold text-slate-900 ml-auto pl-4">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface Bar { label: string; value: number; sub?: string; color?: string }

export function BarList({ bars, testId, unit = "" }: { bars: Bar[]; testId?: string; unit?: string }) {
  const max = Math.max(1, ...bars.map((b) => b.value));
  return (
    <ul className="space-y-3" data-testid={testId}>
      {bars.map((b) => (
        <li key={b.label}>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-slate-700 truncate pr-2">{b.label}</span>
            <span className="font-semibold text-slate-900 shrink-0">{b.value}{unit}{b.sub ? <span className="text-slate-500 font-normal"> · {b.sub}</span> : null}</span>
          </div>
          <div className="h-2.5 rounded-full bg-slate-100 overflow-hidden" role="presentation">
            <div className="h-full rounded-full" style={{ width: `${(b.value / max) * 100}%`, background: b.color ?? "#2563eb", transition: "width 0.8s ease" }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

export function StatCard({ label, value, hint, tone = "brand", icon, testId }: {
  label: string; value: React.ReactNode; hint?: string; tone?: "brand" | "green" | "amber" | "red" | "slate"; icon?: React.ReactNode; testId?: string;
}) {
  const tones = {
    brand: "from-brand-50 text-brand-700", green: "from-emerald-50 text-emerald-700", amber: "from-amber-50 text-amber-700",
    red: "from-red-50 text-red-700", slate: "from-slate-100 text-slate-700",
  } as const;
  return (
    <div className={`card p-5 bg-gradient-to-br ${tones[tone]} to-white animate-slide-up`} data-testid={testId}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide opacity-80">{label}</p>
        {icon && <span className="opacity-70" aria-hidden>{icon}</span>}
      </div>
      <p className="text-3xl font-black text-slate-900 mt-2 tabular-nums">{value}</p>
      {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
    </div>
  );
}
