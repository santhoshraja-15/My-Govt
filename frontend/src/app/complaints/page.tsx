"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { Search, ClipboardList, ArrowLeft, Send, Loader2, CheckCircle2, Clock, AlertTriangle, XCircle, ChevronRight } from "lucide-react";
import { complaints as complaintsAPI } from "@/lib/api";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
  submitted:   { label: "Submitted",   color: "badge-blue",   icon: Clock },
  assigned:    { label: "Assigned",    color: "badge-purple", icon: Clock },
  in_progress: { label: "In Progress", color: "badge-yellow", icon: Clock },
  resolved:    { label: "Resolved",    color: "badge-green",  icon: CheckCircle2 },
  closed:      { label: "Closed",      color: "badge-slate",  icon: CheckCircle2 },
  escalated:   { label: "Escalated",   color: "badge-red",    icon: AlertTriangle },
  rejected:    { label: "Rejected",    color: "badge-red",    icon: XCircle },
};

const PRIORITY_COLORS: Record<string, string> = {
  low: "badge-slate", medium: "badge-yellow", high: "badge-red", critical: "badge-red"
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] || { label: status, color: "badge-slate", icon: Clock };
  const Icon = cfg.icon;
  return (
    <span className={`badge ${cfg.color} flex items-center gap-1`}>
      <Icon size={10} /> {cfg.label}
    </span>
  );
}

function TrackForm() {
  const [ref, setRef] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const track = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ref.trim()) return;
    setLoading(true);
    setError("");
    try {
      const res = await complaintsAPI.track(ref.trim().toUpperCase());
      setResult(res);
    } catch (err: any) {
      setError(err.status === 404 ? "No complaint found with this reference number." : "Failed to fetch. Please try again.");
    }
    setLoading(false);
  };

  return (
    <div className="card p-6">
      <h2 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
        <Search size={20} className="text-brand-600" /> Track Existing Complaint
      </h2>
      <form onSubmit={track} className="flex gap-2 mb-4">
        <input value={ref} onChange={e => setRef(e.target.value)}
          placeholder="Enter reference number e.g. MYG-2024-000001"
          className="input flex-1 font-mono" />
        <button type="submit" disabled={loading} className="btn-primary shrink-0">
          {loading ? <Loader2 size={16} className="animate-spin" /> : "Track"}
        </button>
      </form>
      {error && <p className="text-sm text-red-600 flex items-center gap-1.5"><AlertTriangle size={14} /> {error}</p>}

      {result && (
        <div className="mt-4 space-y-4 animate-slide-up">
          <div className="bg-slate-50 rounded-xl p-4 flex flex-wrap gap-4 justify-between">
            <div>
              <p className="text-xs text-slate-500">Reference</p>
              <p className="font-mono font-bold text-slate-900">{result.reference_number}</p>
            </div>
            <div>
              <p className="text-xs text-slate-500">Status</p>
              <StatusBadge status={result.status} />
            </div>
            <div>
              <p className="text-xs text-slate-500">Priority</p>
              <span className={`badge ${PRIORITY_COLORS[result.priority] || "badge-slate"} capitalize`}>{result.priority}</span>
            </div>
            <div>
              <p className="text-xs text-slate-500">Filed</p>
              <p className="text-sm font-medium">{new Date(result.created_at).toLocaleDateString("en-IN")}</p>
            </div>
          </div>

          <div className="card p-4">
            <p className="text-xs text-slate-500 mb-1">Subject</p>
            <p className="font-semibold text-slate-800">{result.subject}</p>
          </div>

          {result.resolution_due_at && (
            <div className={`rounded-xl p-3 flex items-center gap-2 text-sm ${
              new Date(result.resolution_due_at) < new Date() ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"
            }`}>
              <Clock size={14} className="shrink-0" />
              Resolution expected by: <strong>{new Date(result.resolution_due_at).toLocaleDateString("en-IN")}</strong>
            </div>
          )}

          {result.timeline?.length > 0 && (
            <div className="card p-4">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Timeline</p>
              <div className="space-y-3">
                {result.timeline.map((t: any, i: number) => (
                  <div key={i} className="flex gap-3 items-start">
                    <div className="flex flex-col items-center">
                      <div className="w-2.5 h-2.5 rounded-full bg-brand-400 mt-1.5 shrink-0" />
                      {i < result.timeline.length - 1 && <div className="w-0.5 h-full bg-slate-200 flex-1 mt-1" />}
                    </div>
                    <div className="flex-1 pb-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <StatusBadge status={t.new_status} />
                        <span className="text-xs text-slate-400">{new Date(t.changed_at).toLocaleString("en-IN")}</span>
                      </div>
                      {t.remarks && <p className="text-xs text-slate-500 mt-1">{t.remarks}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ComplaintForm() {
  const [categories, setCategories] = useState<any[]>([]);
  const [form, setForm] = useState({
    subject: "", description: "", category_id: "",
    latitude: "", longitude: "", district_id: "", taluk_id: "",
    contact_name: "", contact_phone: "", contact_email: "",
    anonymous: false,
  });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    complaintsAPI.categories().then(setCategories).catch(() => {});
  }, []);

  const update = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.subject.trim() || !form.description.trim()) {
      setError("Subject and description are required.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const payload: Record<string, any> = {
        subject: form.subject,
        description: form.description,
        category_id: form.category_id || undefined,
        anonymous: form.anonymous,
        latitude: form.latitude ? parseFloat(form.latitude) : undefined,
        longitude: form.longitude ? parseFloat(form.longitude) : undefined,
        district_id: form.district_id ? parseInt(form.district_id) : undefined,
        contact_name: form.contact_name || undefined,
        contact_phone: form.contact_phone || undefined,
        contact_email: form.contact_email || undefined,
      };
      const res = await complaintsAPI.submit(payload);
      setResult(res);
    } catch (err: any) {
      setError(err.message || "Failed to submit complaint. Please try again.");
    }
    setSubmitting(false);
  };

  if (result) return (
    <div className="card p-8 text-center animate-slide-up">
      <CheckCircle2 size={52} className="text-emerald-500 mx-auto mb-4" />
      <h3 className="text-xl font-bold text-slate-900 mb-2">Complaint Filed Successfully</h3>
      <p className="text-slate-500 mb-4">Your reference number is:</p>
      <div className="bg-slate-50 rounded-xl px-6 py-4 mb-6">
        <p className="font-mono text-2xl font-black text-brand-700">{result.reference_number}</p>
      </div>
      <p className="text-sm text-slate-500 mb-6">Save this reference number to track your complaint status.</p>
      <button onClick={() => setResult(null)} className="btn-secondary">File Another Complaint</button>
    </div>
  );

  return (
    <div className="card p-6">
      <h2 className="font-bold text-slate-900 mb-5 flex items-center gap-2">
        <ClipboardList size={20} className="text-brand-600" /> File a New Complaint
      </h2>
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-sm text-red-700 flex items-center gap-2">
            <AlertTriangle size={14} className="shrink-0" /> {error}
          </div>
        )}

        <div>
          <label className="label">Category</label>
          <select className="input" value={form.category_id} onChange={e => update("category_id", e.target.value)}>
            <option value="">— Select Category (optional) —</option>
            {categories.map((c: any) => (
              <option key={c.category_id} value={c.category_id}>{c.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="label">Subject <span className="text-red-500">*</span></label>
          <input className="input" value={form.subject} onChange={e => update("subject", e.target.value)}
            placeholder="Brief description of the issue" maxLength={200} />
        </div>

        <div>
          <label className="label">Description <span className="text-red-500">*</span></label>
          <textarea className="input resize-none" rows={5} value={form.description}
            onChange={e => update("description", e.target.value)}
            placeholder="Provide detailed information about your complaint…" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="label">Latitude (optional)</label>
            <input className="input font-mono" value={form.latitude} onChange={e => update("latitude", e.target.value)}
              placeholder="e.g. 13.0827" />
          </div>
          <div>
            <label className="label">Longitude (optional)</label>
            <input className="input font-mono" value={form.longitude} onChange={e => update("longitude", e.target.value)}
              placeholder="e.g. 80.2707" />
          </div>
        </div>

        <div className="border-t border-slate-100 pt-4">
          <p className="text-sm font-medium text-slate-700 mb-3">Contact Information (optional)</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <input className="input" placeholder="Your name" value={form.contact_name} onChange={e => update("contact_name", e.target.value)} />
            <input className="input" placeholder="Phone number" value={form.contact_phone} onChange={e => update("contact_phone", e.target.value)} />
            <input className="input" type="email" placeholder="Email" value={form.contact_email} onChange={e => update("contact_email", e.target.value)} />
          </div>
        </div>

        <label className="flex items-center gap-2.5 cursor-pointer">
          <input type="checkbox" className="w-4 h-4 rounded accent-brand-600"
            checked={form.anonymous} onChange={e => update("anonymous", e.target.checked)} />
          <span className="text-sm text-slate-600">Submit anonymously</span>
        </label>

        <button type="submit" disabled={submitting} className="btn-primary w-full justify-center text-base py-3">
          {submitting ? <><Loader2 size={18} className="animate-spin" /> Submitting…</> : <><Send size={18} /> Submit Complaint</>}
        </button>
      </form>
    </div>
  );
}

export default function ComplaintsPage() {
  const [activeTab, setActiveTab] = useState<"file" | "track">("file");

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-gradient-to-r from-rose-800 to-rose-600 text-white py-12">
        <div className="max-w-3xl mx-auto px-4">
          <Link href="/" className="inline-flex items-center gap-1.5 text-rose-200 hover:text-white text-sm mb-4 transition-colors">
            <ArrowLeft size={16} /> Home
          </Link>
          <div className="flex items-center gap-3 mb-2">
            <ClipboardList size={30} className="text-rose-300" />
            <h1 className="text-3xl font-black">Complaints</h1>
          </div>
          <p className="text-rose-200">File civic complaints and track resolution status with SLA timelines</p>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex gap-1 bg-white rounded-xl p-1 border border-slate-200 mb-6">
          {[{ key: "file", label: "File Complaint" }, { key: "track", label: "Track Status" }].map(t => (
            <button key={t.key} onClick={() => setActiveTab(t.key as any)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === t.key ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-50"}`}>
              {t.label}
            </button>
          ))}
        </div>

        {activeTab === "file" ? <ComplaintForm /> : <TrackForm />}
      </div>
    </div>
  );
}
