"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Search, ClipboardList, Send, Loader2, CheckCircle2, Clock, AlertTriangle, XCircle, MapPin } from "lucide-react";
import { complaints as complaintsAPI, gis as gisAPI } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLang } from "@/lib/i18n";
import { assignmentText } from "@/lib/complaints";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/AsyncState";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  submitted:    { label: "Submitted",     color: "badge-blue",   icon: Clock },
  needs_triage: { label: "Awaiting triage", color: "badge-yellow", icon: Clock },
  classified:   { label: "Classified",    color: "badge-blue",   icon: Clock },
  assigned:     { label: "Assigned",      color: "badge-purple", icon: Clock },
  in_progress:  { label: "In Progress",   color: "badge-yellow", icon: Clock },
  resolved:     { label: "Resolved",      color: "badge-green",  icon: CheckCircle2 },
  closed:       { label: "Closed",        color: "badge-slate",  icon: CheckCircle2 },
  escalated:    { label: "Escalated",     color: "badge-red",    icon: AlertTriangle },
  reopened:     { label: "Reopened",      color: "badge-yellow", icon: Clock },
  rejected:     { label: "Rejected",      color: "badge-red",    icon: XCircle },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || { label: status, color: "badge-slate", icon: Clock };
  const Icon = cfg.icon;
  return (
    <span className={`badge ${cfg.color} flex items-center gap-1`} data-testid="status-badge" data-status={status}>
      <Icon size={10} /> {cfg.label}
    </span>
  );
}

function fmt(d?: string | null) { return d ? new Date(d).toLocaleString("en-IN") : "—"; }

function ComplaintSummary({ c }: { c: any }) {
  return (
    <div className="space-y-4" data-testid="complaint-summary">
      <div className="bg-slate-50 rounded-xl p-4 flex flex-wrap gap-4 justify-between">
        <div><p className="text-xs text-slate-500">Reference</p><p className="font-mono font-bold text-slate-900" data-testid="reference">{c.reference_number}</p></div>
        <div><p className="text-xs text-slate-500">Status</p><StatusBadge status={c.status} /></div>
        <div><p className="text-xs text-slate-500">Filed</p><p className="text-sm font-medium">{fmt(c.created_at)}</p></div>
      </div>
      <div className="card p-4">
        <p className="text-xs text-slate-500 mb-1">Subject</p>
        <p className="font-semibold text-slate-800">{c.title}</p>
        {c.category_name && <p className="text-xs text-slate-500 mt-1">Category: {c.category_name}</p>}
      </div>
      <div className="card p-4" data-testid="assignment">
        <p className="text-xs text-slate-500 mb-1">Routing</p>
        <p className="text-sm text-slate-700" data-state={c.assignment_state}>{assignmentText(c.assignment_state, c.department_name, c.authority_name)}</p>
      </div>
      {c.due_date && (
        <div data-testid="sla" className={`rounded-xl p-3 flex items-center gap-2 text-sm ${c.sla_breached ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>
          <Clock size={14} className="shrink-0" />
          {c.sla_breached ? "Resolution target missed: " : "Resolution target: "}<strong>{fmt(c.due_date)}</strong>
          <span className="text-xs opacity-70">(platform target, not a statutory guarantee)</span>
        </div>
      )}
      {c.timeline?.length > 0 && (
        <div className="card p-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Timeline</p>
          <ol className="space-y-3">
            {c.timeline.map((t: any, i: number) => (
              <li key={i} className="flex gap-3 items-start">
                <div className="w-2.5 h-2.5 rounded-full bg-brand-400 mt-1.5 shrink-0" />
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <StatusBadge status={t.new_status} />
                    <span className="text-xs text-slate-500">{fmt(t.changed_at)}</span>
                  </div>
                  {t.remarks && <p className="text-xs text-slate-500 mt-1">{t.remarks}</p>}
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

function TrackForm({ initialRef = "" }: { initialRef?: string }) {
  const [ref, setRef] = useState(initialRef);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const track = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!ref.trim()) return;
    setLoading(true); setError(""); setResult(null);
    try {
      setResult(await complaintsAPI.track(ref.trim().toUpperCase()));
    } catch (err: any) {
      setError(err.status === 404 ? "No complaint found with this reference number." : err.message || "Failed to fetch. Please try again.");
    }
    setLoading(false);
  };

  return (
    <div className="card p-6">
      <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2"><Search size={20} className="text-brand-600" /> Track Existing Complaint</h2>
      <form onSubmit={track} className="flex gap-2 mb-4">
        <label htmlFor="track-ref" className="sr-only">Reference number</label>
        <input id="track-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="Reference number e.g. MYG-2026-000001" className="input flex-1 font-mono" />
        <button type="submit" disabled={loading} className="btn-primary shrink-0">{loading ? <Loader2 size={16} className="animate-spin" /> : "Track"}</button>
      </form>
      {error && <p role="alert" className="text-sm text-red-600 flex items-center gap-1.5"><AlertTriangle size={14} /> {error}</p>}
      {result && <div className="mt-4"><ComplaintSummary c={result} /></div>}
    </div>
  );
}

function LoginPrompt({ what }: { what: string }) {
  const { t } = useLang();
  return (
    <div className="card p-8 text-center" data-testid="login-required">
      <p className="text-slate-700 mb-4">{t("auth.required")} ({what})</p>
      <div className="flex justify-center gap-3">
        <Link href="/login?next=/complaints" className="btn-primary">{t("auth.signin")}</Link>
        <Link href="/register?next=/complaints" className="btn-secondary">{t("auth.register")}</Link>
      </div>
    </div>
  );
}

function ComplaintForm() {
  const { user, loading: authLoading } = useAuth();
  const { t, pick } = useLang();
  const [categories, setCategories] = useState<any[]>([]);
  const [districts, setDistricts] = useState<any[]>([]);
  const [form, setForm] = useState({ title: "", description: "", category_id: "", district_id: "", address: "", latitude: "", longitude: "", is_anonymous: false, locationConsent: false });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const [metaError, setMetaError] = useState(false);

  const loadMeta = useCallback(() => {
    setMetaError(false);
    complaintsAPI.categories().then(setCategories).catch(() => setMetaError(true));
    gisAPI.districts().then(setDistricts).catch(() => setMetaError(true));
  }, []);
  useEffect(() => { loadMeta(); }, [loadMeta]);

  const update = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));
  const hasCoords = form.latitude.trim() !== "" || form.longitude.trim() !== "";

  const useMyLocation = () => {
    if (!navigator.geolocation) { setError("Your browser does not support location."); return; }
    navigator.geolocation.getCurrentPosition(
      (p) => { update("latitude", p.coords.latitude.toFixed(6)); update("longitude", p.coords.longitude.toFixed(6)); },
      () => setError("Could not read your location. You can type the coordinates or leave them blank."),
    );
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (form.title.trim().length < 3) return setError("Subject must be at least 3 characters.");
    if (form.description.trim().length < 10) return setError("Description must be at least 10 characters.");
    const lat = form.latitude.trim() === "" ? undefined : Number(form.latitude);
    const lon = form.longitude.trim() === "" ? undefined : Number(form.longitude);
    if ((lat === undefined) !== (lon === undefined)) return setError("Provide both latitude and longitude, or neither.");
    if (lat !== undefined && (Number.isNaN(lat) || lat < -90 || lat > 90)) return setError("Latitude must be a number between -90 and 90.");
    if (lon !== undefined && (Number.isNaN(lon) || lon < -180 || lon > 180)) return setError("Longitude must be a number between -180 and 180.");
    if (hasCoords && !form.locationConsent) return setError("Please confirm you agree to share your location.");

    setSubmitting(true);
    try {
      setResult(await complaintsAPI.submit({
        title: form.title.trim(),
        description: form.description.trim(),
        category_id: form.category_id ? Number(form.category_id) : undefined,
        district_id: form.district_id ? Number(form.district_id) : undefined,
        address: form.address.trim() || undefined,
        latitude: lat, longitude: lon,
        is_anonymous: form.is_anonymous,
      }));
    } catch (err: any) {
      setError(err.status === 401 ? "Your session has expired. Please sign in again." : err.message || "Failed to submit complaint. Please try again.");
    }
    setSubmitting(false);
  };

  if (authLoading) return <LoadingState label={t("common.loading")} />;
  if (!user) return <LoginPrompt what="file a complaint" />;

  if (result) return (
    <div className="card p-8 text-center" data-testid="submit-success">
      <CheckCircle2 size={52} className="text-emerald-500 mx-auto mb-4" />
      <h3 className="text-xl font-bold text-slate-900 mb-2">Complaint Filed Successfully</h3>
      <p className="text-slate-500 mb-4">Your reference number is:</p>
      <div className="bg-slate-50 rounded-xl px-6 py-4 mb-4"><p className="font-mono text-2xl font-black text-brand-700" data-testid="new-reference">{result.reference_number}</p></div>
      <p className="text-sm text-slate-600 mb-2" data-testid="assignment-text">{assignmentText(result.assignment_state, result.department_name)}</p>
      {result.due_date && <p className="text-sm text-slate-500 mb-4">Resolution target: {fmt(result.due_date)}</p>}
      {form.is_anonymous && <p className="text-xs text-amber-700 mb-4">Anonymous complaints cannot be tracked publicly. Keep your reference for the department.</p>}
      <button onClick={() => { setResult(null); setForm({ ...form, title: "", description: "" }); }} className="btn-secondary">File Another Complaint</button>
    </div>
  );

  return (
    <div className="card p-6">
      <h2 className="font-bold text-slate-900 mb-5 flex items-center gap-2"><ClipboardList size={20} className="text-brand-600" /> {t("complaint.title")}</h2>
      {metaError && <ErrorState message="Could not load categories or districts." onRetry={loadMeta} retryLabel={t("common.retry")} />}
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error && <div role="alert" className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700 flex items-center gap-2"><AlertTriangle size={14} className="shrink-0" /> {error}</div>}

        <div>
          <label htmlFor="category" className="label">{t("complaint.category")}</label>
          <select id="category" className="input" value={form.category_id} onChange={(e) => update("category_id", e.target.value)}>
            <option value="">— optional —</option>
            {categories.map((c: any) => <option key={c.category_id} value={c.category_id}>{pick(c.name, c.name_ta)}</option>)}
          </select>
          <p className="text-xs text-slate-500 mt-1">Choosing a category lets us route the complaint to a department. Without one it waits for manual triage.</p>
        </div>

        <div>
          <label htmlFor="title" className="label">{t("complaint.subject")} <span className="text-red-500">*</span></label>
          <input id="title" aria-required="true" className="input" value={form.title} onChange={(e) => update("title", e.target.value)} maxLength={200} />
        </div>
        <div>
          <label htmlFor="description" className="label">{t("complaint.description")} <span className="text-red-500">*</span></label>
          <textarea id="description" aria-required="true" className="input resize-none" rows={5} value={form.description} onChange={(e) => update("description", e.target.value)} maxLength={5000} />
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="district" className="label">District</label>
            <select id="district" className="input" value={form.district_id} onChange={(e) => update("district_id", e.target.value)}>
              <option value="">— optional —</option>
              {districts.map((d: any) => <option key={d.district_id} value={d.district_id}>{pick(d.district_name, d.district_name_ta)}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="address" className="label">Address / landmark</label>
            <input id="address" className="input" value={form.address} onChange={(e) => update("address", e.target.value)} maxLength={500} />
          </div>
        </div>

        <fieldset className="border border-slate-200 rounded-xl p-4">
          <legend className="text-sm font-medium text-slate-700 px-1">Exact location (optional)</legend>
          <div className="grid grid-cols-2 gap-4">
            <div><label htmlFor="lat" className="label">Latitude</label><input id="lat" className="input font-mono" inputMode="decimal" value={form.latitude} onChange={(e) => update("latitude", e.target.value)} placeholder="13.0827" /></div>
            <div><label htmlFor="lon" className="label">Longitude</label><input id="lon" className="input font-mono" inputMode="decimal" value={form.longitude} onChange={(e) => update("longitude", e.target.value)} placeholder="80.2707" /></div>
          </div>
          <button type="button" onClick={useMyLocation} className="btn-secondary mt-3 inline-flex items-center gap-1.5"><MapPin size={14} /> Use my current location</button>
          {hasCoords && (
            <label className="flex items-start gap-2.5 mt-3 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 mt-0.5 rounded accent-brand-600" checked={form.locationConsent} onChange={(e) => update("locationConsent", e.target.checked)} />
              <span className="text-sm text-slate-600">{t("complaint.location.consent")}</span>
            </label>
          )}
        </fieldset>

        <label className="flex items-center gap-2.5 cursor-pointer">
          <input type="checkbox" className="w-4 h-4 rounded accent-brand-600" checked={form.is_anonymous} onChange={(e) => update("is_anonymous", e.target.checked)} />
          <span className="text-sm text-slate-600">Hide my identity from the public tracking page</span>
        </label>

        <button type="submit" disabled={submitting} className="btn-primary w-full justify-center text-base py-3">
          {submitting ? <><Loader2 size={18} className="animate-spin" /> Submitting…</> : <><Send size={18} /> {t("complaint.submit")}</>}
        </button>
      </form>
    </div>
  );
}

function MyComplaints({ onTrack }: { onTrack: (ref: string) => void }) {
  const { user, loading: authLoading } = useAuth();
  const { t } = useLang();
  const [items, setItems] = useState<any[] | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setItems(null); setError("");
    complaintsAPI.mine({ page_size: 50 }).then((r) => setItems(r.items)).catch((e) => setError(e.message || t("common.error")));
  }, [t]);
  useEffect(() => { if (user) load(); }, [user, load]);

  if (authLoading) return <LoadingState label={t("common.loading")} />;
  if (!user) return <LoginPrompt what="see your complaints" />;
  if (error) return <ErrorState message={error} onRetry={load} retryLabel={t("common.retry")} />;
  if (items === null) return <LoadingState label={t("common.loading")} />;
  if (items.length === 0) return <EmptyState message="You have not filed any complaints yet." />;
  return (
    <ul className="space-y-3" data-testid="my-complaints">
      {items.map((c) => (
        <li key={c.complaint_id} className="card p-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="font-semibold text-slate-800 truncate">{c.title}</p>
            <p className="text-xs text-slate-500 font-mono">{c.reference_number} · {fmt(c.created_at)}</p>
            <p className="text-xs text-slate-500 mt-1">{assignmentText(c.assignment_state, c.department_name)}</p>
          </div>
          <div className="flex flex-col items-end gap-2 shrink-0">
            <StatusBadge status={c.status} />
            <button type="button" className="text-xs text-brand-700 underline" onClick={() => onTrack(c.reference_number)}>Details</button>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function ComplaintsPage() {
  const { t } = useLang();
  const [activeTab, setActiveTab] = useState<"file" | "track" | "mine">("file");
  const [trackRef, setTrackRef] = useState("");
  const tabs = [
    { key: "file", label: "File Complaint" },
    { key: "track", label: "Track Status" },
    { key: "mine", label: t("complaint.mine") },
  ] as const;

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-rose-800 to-rose-600 text-white py-10">
        <div className="max-w-3xl mx-auto px-4">
          <div className="flex items-center gap-3 mb-2"><ClipboardList size={30} className="text-rose-300" /><h1 className="text-3xl font-black">{t("nav.complaints")}</h1></div>
          <p className="text-rose-200">File civic complaints and track their routing and resolution target.</p>
        </div>
      </div>
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div role="tablist" className="flex gap-1 bg-white rounded-xl p-1 border border-slate-200 mb-6">
          {tabs.map((tab) => (
            <button key={tab.key} role="tab" aria-selected={activeTab === tab.key} onClick={() => setActiveTab(tab.key)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${activeTab === tab.key ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"}`}>
              {tab.label}
            </button>
          ))}
        </div>
        {activeTab === "file" && <ComplaintForm />}
        {activeTab === "track" && <TrackForm key={trackRef} initialRef={trackRef} />}
        {activeTab === "mine" && <MyComplaints onTrack={(r) => { setTrackRef(r); setActiveTab("track"); }} />}
      </main>
    </div>
  );
}
