"use client";

import Link from "next/link";
import { publicStats } from "@/lib/api";
import { AuthNav } from "@/components/layout/AuthNav";
import { LangToggle } from "@/components/layout/LangToggle";
import { useLang, type TKey } from "@/lib/i18n";
import { useState, useEffect } from "react";
import {
  Search, MessageSquare, FileText, MapPin, ClipboardList,
  Shield, Zap, Globe, ChevronRight, ArrowRight, Star,
  Users, Building2, Award, TrendingUp, Bell, Menu, X
} from "lucide-react";

// ── Typed words for hero ──────────────────────────────────────
const TYPED_KEYS = ["home.typed.schemes", "home.typed.services", "home.typed.benefits", "home.typed.answers", "home.typed.information"] as const;

function TypedWord() {
  const { t, lang } = useLang();
  const TYPED_WORDS = TYPED_KEYS.map((k) => t(k));
  const [index, setIndex] = useState(0);
  const [displayed, setDisplayed] = useState("");
  const [deleting, setDeleting] = useState(false);

  useEffect(() => { setDisplayed(""); setDeleting(false); }, [lang]);

  useEffect(() => {
    const word = TYPED_WORDS[index];
    let timeout: NodeJS.Timeout;

    if (!deleting && displayed.length < word.length) {
      timeout = setTimeout(() => setDisplayed(word.slice(0, displayed.length + 1)), 80);
    } else if (!deleting && displayed.length === word.length) {
      timeout = setTimeout(() => setDeleting(true), 2000);
    } else if (deleting && displayed.length > 0) {
      timeout = setTimeout(() => setDisplayed(displayed.slice(0, -1)), 45);
    } else if (deleting && displayed.length === 0) {
      setDeleting(false);
      setIndex((i) => (i + 1) % TYPED_WORDS.length);
    }
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [displayed, deleting, index, lang]);

  return (
    <span className="text-saffron-400">
      {displayed}
      <span className="animate-pulse">|</span>
    </span>
  );
}

// ── Navigation ────────────────────────────────────────────────
function Navbar() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${scrolled ? "glass-dark shadow-xl" : "bg-transparent"}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/logo-128.png" alt="" width={40} height={40} className="w-10 h-10 rounded-full bg-white shadow-lg" />
            <div className="flex flex-col leading-tight">
              <span className="text-white font-bold text-base">MyGovt</span>
              <span className="text-blue-200 text-[10px] font-medium">{t("home.brand.sub")}</span>
            </div>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-1">
            {[
              { href: "/schemes", label: t("nav.schemes") },
              { href: "/services", label: t("nav.services") },
              { href: "/documents", label: t("nav.documents") },
              { href: "/complaints", label: t("nav.complaints") },
              { href: "/assistant", label: t("nav.assistant") },
            ].map((item) => (
              <Link key={item.href} href={item.href}
                className="px-3 py-2 rounded-lg text-sm font-medium text-blue-100 hover:text-white hover:bg-white/10 transition-all">
                {item.label}
              </Link>
            ))}
          </div>

          {/* Auth buttons */}
          <div className="hidden md:flex items-center gap-3">
            <LangToggle />
            <AuthNav />
          </div>

          {/* Mobile menu */}
          <button onClick={() => setOpen(!open)} className="md:hidden text-white p-2" aria-label={t("home.toggleNav")} aria-expanded={open}>
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {open && (
        <div className="md:hidden glass-dark border-t border-white/10 px-4 py-3 space-y-1">
          {([["/schemes", "nav.schemes"], ["/services", "nav.services"], ["/documents", "nav.documents"], ["/complaints", "nav.complaints"], ["/assistant", "nav.assistant"]] as [string, TKey][]).map(([href, key]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}
              className="block px-3 py-2 text-sm text-blue-100 hover:text-white hover:bg-white/10 rounded-lg">
              {t(key)}
            </Link>
          ))}
          <div className="flex gap-3 pt-2"><LangToggle className="shrink-0" />
            <Link href="/login" className="flex-1 text-center py-2 text-sm text-blue-200 border border-white/20 rounded-xl">{t("auth.signin")}</Link>
            <Link href="/register" className="flex-1 text-center py-2 text-sm text-white bg-saffron-500 rounded-xl font-semibold">{t("auth.register")}</Link>
          </div>
        </div>
      )}
    </nav>
  );
}

// ── Stats ─────────────────────────────────────────────────────
// Counts come from GET /api/v1/public/stats (live database counts); nothing here is hardcoded.
const STAT_DEFS = [
  { key: "schemes", label: "home.stat.schemes", icon: Award },
  { key: "districts", label: "home.stat.districts", icon: MapPin },
  { key: "services", label: "home.stat.services", icon: Building2 },
  { key: "departments", label: "home.stat.departments", icon: Users },
] as const;

// ── Quick actions ─────────────────────────────────────────────
const QUICK_ACTIONS = [
  { href: "/schemes", icon: Award, k: "schemes", color: "from-blue-500 to-blue-700" },
  { href: "/assistant", icon: MessageSquare, k: "assistant", color: "from-purple-500 to-purple-700" },
  { href: "/complaints", icon: ClipboardList, k: "complaints", color: "from-rose-500 to-rose-700" },
  { href: "/services", icon: FileText, k: "services", color: "from-emerald-500 to-emerald-700" },
  { href: "/documents", icon: Globe, k: "documents", color: "from-indigo-500 to-indigo-700" },
];

// ── Feature cards ─────────────────────────────────────────────
const FEATURES = [
  { icon: Shield, k: "f1" },
  { icon: Zap, k: "f2" },
  { icon: Globe, k: "f3" },
  { icon: TrendingUp, k: "f4" },
];

// ── Popular schemes ───────────────────────────────────────────
const POPULAR_SCHEMES = [
  { name: "Kalaignar Magalir Urimai Thogai", ta: "கலைஞர் மகளிர் உரிமைத் தொகை", dept: "home.pop.dept.social", tag: "status.provisional", color: "badge-yellow" },
  { name: "CMCHIS (Health Insurance)", ta: "முதலமைச்சரின் விரிவான மருத்துவக் காப்பீடு", dept: "home.pop.dept.health", tag: "status.provisional", color: "badge-yellow" },
  { name: "Pudhumai Penn", ta: "புதுமைப் பெண் திட்டம்", dept: "home.pop.dept.education", tag: "status.provisional", color: "badge-yellow" },
  { name: "PM-Kisan", ta: "பிரதம மந்திரி கிசான் சம்மான் நிதி", dept: "home.pop.dept.agri", tag: "status.external", color: "badge-blue" },
  { name: "Vidiyal Payanam", ta: "விடியல் பயணம்", dept: "home.pop.dept.transport", tag: "status.provisional", color: "badge-yellow" },
  { name: "Old Age Pension", ta: "முதியோர் ஓய்வூதியம்", dept: "home.pop.dept.social", tag: "status.provisional", color: "badge-yellow" },
];

// ── Main page ─────────────────────────────────────────────────
export default function HomePage() {
  const { t, names } = useLang();
  const [searchQuery, setSearchQuery] = useState("");
  const [liveStats, setLiveStats] = useState<Record<string, number> | null>(null);
  useEffect(() => { publicStats.get().then(setLiveStats).catch(() => setLiveStats(null)); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      window.location.href = `/schemes?q=${encodeURIComponent(searchQuery)}`;
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar />

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section className="hero-gradient min-h-[92vh] flex flex-col items-center justify-center relative overflow-hidden pt-16">
        {/* Decorative blobs */}
        <div className="absolute top-20 -left-32 w-96 h-96 bg-blue-400/20 rounded-full blur-3xl" />
        <div className="absolute bottom-0 -right-32 w-96 h-96 bg-teal-400/20 rounded-full blur-3xl" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-600/10 rounded-full blur-3xl" />

        <div className="relative z-10 max-w-5xl mx-auto px-4 text-center">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 glass rounded-full px-4 py-1.5 mb-6 animate-fade-in">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse-slow" />
            <span className="text-blue-100 text-sm font-medium">{t("home.badge")}</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-black text-white leading-tight mb-6 animate-slide-up">
            {t("home.h1a")}<br />
            {t("home.h1b")} <TypedWord />.
          </h1>

          <p className="text-lg md:text-xl text-blue-200 max-w-2xl mx-auto mb-10 font-medium animate-fade-in">
            {t("home.lead")}
          </p>

          {/* Search bar */}
          <form onSubmit={handleSearch} className="max-w-2xl mx-auto mb-8 animate-slide-up">
            <div className="flex gap-2 glass rounded-2xl p-2 shadow-2xl">
              <div className="flex-1 flex items-center gap-3 px-4">
                <Search size={20} className="text-blue-300 shrink-0" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder={t("home.searchPlaceholder")} aria-label={t("home.searchLabel")} data-testid="landing-search"
                  className="flex-1 min-w-0 bg-transparent text-white placeholder-blue-300 text-sm outline-none"
                />
              </div>
              <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shrink-0">
                {t("common.search")} <ArrowRight size={16} />
              </button>
            </div>
          </form>

          {/* Popular searches */}
          <div className="flex flex-wrap items-center justify-center gap-2 animate-fade-in">
            <span className="text-blue-300 text-sm">{t("home.popular")}</span>
            {([["Kalaignar Magalir Urimai", "home.pop1"], ["CM Health Insurance", "home.pop2"], ["Old Age Pension", "home.pop3"], ["Free Bus Pass", "home.pop4"]] as [string, TKey][]).map(([term, key]) => (
              <Link key={term} href={`/schemes?q=${encodeURIComponent(term)}`}
                className="text-sm glass hover:bg-white/20 text-blue-100 px-3 py-1 rounded-full transition-all">
                {t(key)}
              </Link>
            ))}
          </div>
        </div>

        {/* Stats band */}
        <div className="relative z-10 w-full max-w-5xl mx-auto px-4 mt-16">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STAT_DEFS.map(({ key, label, icon: Icon }) => (
              <div key={label} className="glass rounded-2xl p-5 text-center animate-fade-in" data-testid={`stat-${key}`}>
                <Icon size={24} className="text-saffron-400 mx-auto mb-2" />
                <div className="text-3xl font-black text-white">{liveStats ? liveStats[key] : "—"}</div>
                <div className="text-blue-200 text-xs font-medium mt-1">{t(label as TKey)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Quick Actions ─────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-4 py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">
            {t("home.q.title")}
          </h2>
          <p className="text-slate-500 text-lg">{t("home.q.sub")}</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {QUICK_ACTIONS.map(({ href, icon: Icon, k, color }) => (
            <Link key={href} href={href}
              className="group card p-6 flex gap-4 items-start hover:border-brand-200">
              <div className={`shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-200`}>
                <Icon size={22} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-slate-900 mb-1 group-hover:text-brand-700 transition-colors">{t(`home.qa.${k}.title` as TKey)}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{t(`home.qa.${k}.desc` as TKey)}</p>
              </div>
              <ChevronRight size={18} className="text-slate-300 group-hover:text-brand-500 group-hover:translate-x-1 transition-all shrink-0 mt-0.5" />
            </Link>
          ))}
        </div>
      </section>

      {/* ── Popular Schemes ───────────────────────────────────── */}
      <section className="bg-gradient-to-br from-brand-950 to-slate-900 py-20">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between mb-10">
            <div>
              <h2 className="text-3xl font-bold text-white mb-2">{t("home.pop.title")}</h2>
              <p className="text-blue-300">{t("home.pop.sub")}</p>
            </div>
            <Link href="/schemes" className="btn-secondary bg-transparent border-blue-300 text-blue-100 hover:bg-white/10">
              {t("home.pop.viewAll")} <ChevronRight size={16} />
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {POPULAR_SCHEMES.map(({ name, ta, dept, tag, color }) => (
              <Link key={name} href={`/schemes?q=${encodeURIComponent(name)}`}
                className="group flex items-center gap-4 glass hover:bg-white/15 rounded-2xl p-4 transition-all duration-200">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-saffron-400 to-brand-600 flex items-center justify-center shrink-0">
                  <Star size={16} className="text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-semibold text-sm truncate" title={names(name, ta).text} data-i18n-skip>{names(name, ta).primary}</p>
                  <p className="text-blue-200 text-xs truncate" data-i18n-skip>{names(name, ta).secondary}</p>
                  <p className="text-blue-300 text-xs">{t(dept as TKey)}</p>
                </div>
                <span className={`badge text-xs shrink-0 ${color}`}>{t(tag as TKey)}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why MyGovt ───────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-4 py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">{t("home.why.title")}</h2>
          <p className="text-slate-500 text-lg max-w-xl mx-auto">
            {t("home.why.sub")}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {FEATURES.map(({ icon: Icon, k }) => (
            <div key={k} className="card p-6 flex gap-4">
              <div className="shrink-0 w-11 h-11 rounded-xl bg-brand-50 flex items-center justify-center">
                <Icon size={22} className="text-brand-600" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 mb-1.5">{t(`home.${k}.title` as TKey)}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{t(`home.${k}.desc` as TKey)}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── AI Assistant CTA ──────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-4 pb-20">
        <div className="rounded-3xl bg-gradient-to-r from-brand-600 via-brand-700 to-teal-700 p-10 md:p-16 text-center relative overflow-hidden">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,255,255,0.1),transparent)]" />
          <div className="relative z-10">
            <div className="inline-flex items-center gap-2 bg-white/15 rounded-full px-4 py-1.5 mb-6">
              <MessageSquare size={16} className="text-saffron-300" />
              <span className="text-white text-sm font-medium">{t("home.cta.badge")}</span>
            </div>
            <h2 className="text-3xl md:text-5xl font-black text-white mb-4">
              {t("home.cta.title1")}<br />{t("home.cta.title2")}
            </h2>
            <p className="text-blue-200 text-lg mb-8 max-w-xl mx-auto">
              {t("home.cta.desc")}
            </p>
            <Link href="/assistant" className="inline-flex items-center gap-3 bg-white text-brand-700 font-bold px-8 py-4 rounded-2xl hover:bg-blue-50 transition-all shadow-2xl text-lg">
              <MessageSquare size={22} />
              {t("home.cta.button")}
              <ArrowRight size={20} />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="bg-slate-900 text-slate-300 py-12">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-10">
            <div>
              <div className="flex items-center gap-2 mb-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo-128.png" alt="" width={36} height={36} className="w-9 h-9 rounded-full bg-white" />
                <span className="text-white font-bold">MyGovt</span>
              </div>
              <p className="text-sm leading-relaxed">
                {t("home.footer.tagline")}<br />
                {t("home.footer.place")}
              </p>
            </div>
            {[
              { title: "home.footer.citizen", links: [["home.footer.l.schemes", "/schemes"], ["home.footer.l.services", "/services"], ["home.footer.l.file", "/complaints"], ["home.footer.l.track", "/complaints"]] },
              { title: "home.footer.info", links: [["home.footer.l.documents", "/documents"], ["home.footer.l.assistant", "/assistant"]] },
              { title: "home.footer.account", links: [["home.footer.l.signin", "/login"], ["home.footer.l.register", "/register"]] },
            ].map(({ title, links }) => (
              <div key={title}>
                <h4 className="text-white font-semibold mb-3 text-sm">{t(title as TKey)}</h4>
                <ul className="space-y-2">
                  {links.map(([lk, href]) => (
                    <li key={lk}>
                      <Link href={href} className="text-sm hover:text-white transition-colors">{t(lk as TKey)}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-800 pt-6 flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-xs">{t("home.footer.demo")}</p>
            <p className="text-xs">{t("home.footer.labels")}</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
