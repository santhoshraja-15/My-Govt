"use client";

import Link from "next/link";
import { useState, useEffect } from "react";
import {
  Search, MessageSquare, FileText, MapPin, ClipboardList,
  Shield, Zap, Globe, ChevronRight, ArrowRight, Star,
  Users, Building2, Award, TrendingUp, Bell, Menu, X
} from "lucide-react";

// ── Typed words for hero ──────────────────────────────────────
const TYPED_WORDS = ["Schemes", "Services", "Benefits", "Answers", "Information"];

function TypedWord() {
  const [index, setIndex] = useState(0);
  const [displayed, setDisplayed] = useState("");
  const [deleting, setDeleting] = useState(false);

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
  }, [displayed, deleting, index]);

  return (
    <span className="text-saffron-400">
      {displayed}
      <span className="animate-pulse">|</span>
    </span>
  );
}

// ── Navigation ────────────────────────────────────────────────
function Navbar() {
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
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-saffron-400 to-brand-600 flex items-center justify-center shadow-lg">
              <span className="text-white font-bold text-sm">MG</span>
            </div>
            <div className="flex flex-col leading-tight">
              <span className="text-white font-bold text-base">MyGovt</span>
              <span className="text-blue-200 text-[10px] font-medium">Tamil Nadu</span>
            </div>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-1">
            {[
              { href: "/schemes", label: "Schemes" },
              { href: "/services", label: "Services" },
              { href: "/documents", label: "Documents" },
              { href: "/complaints", label: "Complaints" },
              { href: "/assistant", label: "AI Assistant" },
            ].map((item) => (
              <Link key={item.href} href={item.href}
                className="px-3 py-2 rounded-lg text-sm font-medium text-blue-100 hover:text-white hover:bg-white/10 transition-all">
                {item.label}
              </Link>
            ))}
          </div>

          {/* Auth buttons */}
          <div className="hidden md:flex items-center gap-3">
            <Link href="/login" className="btn-ghost text-blue-100 hover:bg-white/10 hover:text-white">Sign In</Link>
            <Link href="/register" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shadow-saffron-500/30">
              Register Free
            </Link>
          </div>

          {/* Mobile menu */}
          <button onClick={() => setOpen(!open)} className="md:hidden text-white p-2">
            {open ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {open && (
        <div className="md:hidden glass-dark border-t border-white/10 px-4 py-3 space-y-1">
          {["/schemes", "/services", "/documents", "/complaints", "/assistant"].map((href) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}
              className="block px-3 py-2 text-sm text-blue-100 hover:text-white hover:bg-white/10 rounded-lg capitalize">
              {href.slice(1)}
            </Link>
          ))}
          <div className="flex gap-3 pt-2">
            <Link href="/login" className="flex-1 text-center py-2 text-sm text-blue-200 border border-white/20 rounded-xl">Sign In</Link>
            <Link href="/register" className="flex-1 text-center py-2 text-sm text-white bg-saffron-500 rounded-xl font-semibold">Register</Link>
          </div>
        </div>
      )}
    </nav>
  );
}

// ── Stats ─────────────────────────────────────────────────────
const STATS = [
  { value: "30+", label: "Government Schemes", icon: Award },
  { value: "38", label: "Districts Covered", icon: MapPin },
  { value: "20+", label: "Citizen Services", icon: Building2 },
  { value: "75M+", label: "Citizens Served", icon: Users },
];

// ── Quick actions ─────────────────────────────────────────────
const QUICK_ACTIONS = [
  { href: "/schemes", icon: Award, title: "Find Schemes", desc: "Discover benefits you qualify for", color: "from-blue-500 to-blue-700" },
  { href: "/assistant", icon: MessageSquare, title: "AI Assistant", desc: "Ask anything about government services", color: "from-purple-500 to-purple-700" },
  { href: "/complaints", icon: ClipboardList, title: "File Complaint", desc: "Report civic issues & track resolution", color: "from-rose-500 to-rose-700" },
  { href: "/services", icon: FileText, title: "Get Certificates", desc: "Apply for nativity, income, community & more", color: "from-emerald-500 to-emerald-700" },
  { href: "/locations", icon: MapPin, title: "Find Offices", desc: "Locate nearest e-Sevai & government offices", color: "from-amber-500 to-amber-700" },
  { href: "/documents", icon: Globe, title: "Policy Documents", desc: "Access GOs, policies and official documents", color: "from-indigo-500 to-indigo-700" },
];

// ── Feature cards ─────────────────────────────────────────────
const FEATURES = [
  { icon: Shield, title: "Source-Grounded Answers", desc: "Answers come only from the records we hold, each labelled Verified, Provisional or External — no invented facts." },
  { icon: Zap, title: "Real-time AI Eligibility", desc: "Get instant, deterministic eligibility checks for 30+ Tamil Nadu schemes based on your profile." },
  { icon: Globe, title: "Bilingual — English & Tamil", desc: "Ask questions and read answers in English or Tamil. Full UI available in both languages." },
  { icon: TrendingUp, title: "End-to-End Complaint Tracking", desc: "File, track, and escalate civic complaints with SLA timelines and real-time status updates." },
];

// ── Popular schemes ───────────────────────────────────────────
const POPULAR_SCHEMES = [
  { name: "Kalaignar Magalir Urimai", dept: "Social Welfare", tag: "₹1,000/month", color: "badge-purple" },
  { name: "CM Health Insurance", dept: "Health", tag: "₹5L cover", color: "badge-blue" },
  { name: "Old Age Pension", dept: "Social Welfare", tag: "₹1,000/month", color: "badge-green" },
  { name: "PM-Kisan", dept: "Agriculture", tag: "₹6,000/year", color: "badge-yellow" },
  { name: "Free Laptop Scheme", dept: "Education", tag: "Students", color: "badge-blue" },
  { name: "Free Bus Pass for Women", dept: "Transport", tag: "All Women", color: "badge-green" },
];

// ── Main page ─────────────────────────────────────────────────
export default function HomePage() {
  const [searchQuery, setSearchQuery] = useState("");

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
            <span className="text-blue-100 text-sm font-medium">Official AI-Powered Platform — Tamil Nadu Government</span>
          </div>

          <h1 className="text-5xl md:text-7xl font-black text-white leading-tight mb-6 animate-slide-up">
            Your Government.<br />
            Your <TypedWord />.
          </h1>

          <p className="text-lg md:text-xl text-blue-200 max-w-2xl mx-auto mb-10 font-medium animate-fade-in">
            Discover 30+ government schemes, get instant eligibility checks, track complaints, and access all Tamil Nadu citizen services — powered by AI.
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
                  placeholder="Search schemes, services, or ask a question…"
                  className="flex-1 bg-transparent text-white placeholder-blue-300 text-sm outline-none"
                />
              </div>
              <button type="submit" className="btn-primary bg-saffron-500 hover:bg-saffron-600 shrink-0">
                Search <ArrowRight size={16} />
              </button>
            </div>
          </form>

          {/* Popular searches */}
          <div className="flex flex-wrap items-center justify-center gap-2 animate-fade-in">
            <span className="text-blue-300 text-sm">Popular:</span>
            {["Kalaignar Magalir Urimai", "CM Health Insurance", "Old Age Pension", "Free Bus Pass"].map((term) => (
              <Link key={term} href={`/schemes?q=${encodeURIComponent(term)}`}
                className="text-sm glass hover:bg-white/20 text-blue-100 px-3 py-1 rounded-full transition-all">
                {term}
              </Link>
            ))}
          </div>
        </div>

        {/* Stats band */}
        <div className="relative z-10 w-full max-w-5xl mx-auto px-4 mt-16">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {STATS.map(({ value, label, icon: Icon }) => (
              <div key={label} className="glass rounded-2xl p-5 text-center animate-fade-in">
                <Icon size={24} className="text-saffron-400 mx-auto mb-2" />
                <div className="text-3xl font-black text-white">{value}</div>
                <div className="text-blue-200 text-xs font-medium mt-1">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Quick Actions ─────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-4 py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">
            What would you like to do?
          </h2>
          <p className="text-slate-500 text-lg">Everything you need — in one place</p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {QUICK_ACTIONS.map(({ href, icon: Icon, title, desc, color }) => (
            <Link key={href} href={href}
              className="group card p-6 flex gap-4 items-start hover:border-brand-200">
              <div className={`shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br ${color} flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-200`}>
                <Icon size={22} className="text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-slate-900 mb-1 group-hover:text-brand-700 transition-colors">{title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
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
              <h2 className="text-3xl font-bold text-white mb-2">Popular Schemes</h2>
              <p className="text-blue-300">Most accessed government benefit programmes</p>
            </div>
            <Link href="/schemes" className="btn-secondary border-blue-700 text-blue-300 hover:bg-blue-900">
              View All <ChevronRight size={16} />
            </Link>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {POPULAR_SCHEMES.map(({ name, dept, tag, color }) => (
              <Link key={name} href={`/schemes?q=${encodeURIComponent(name)}`}
                className="group flex items-center gap-4 glass hover:bg-white/15 rounded-2xl p-4 transition-all duration-200">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-saffron-400 to-brand-600 flex items-center justify-center shrink-0">
                  <Star size={16} className="text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-semibold text-sm truncate">{name}</p>
                  <p className="text-blue-300 text-xs">{dept}</p>
                </div>
                <span className={`badge text-xs shrink-0 ${color}`}>{tag}</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why MyGovt ───────────────────────────────────────── */}
      <section className="max-w-7xl mx-auto px-4 py-20">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-900 mb-3">Why MyGovt?</h2>
          <p className="text-slate-500 text-lg max-w-xl mx-auto">
            Built on verified government data, grounded AI, and a commitment to no misinformation
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <div key={title} className="card p-6 flex gap-4">
              <div className="shrink-0 w-11 h-11 rounded-xl bg-brand-50 flex items-center justify-center">
                <Icon size={22} className="text-brand-600" />
              </div>
              <div>
                <h3 className="font-bold text-slate-900 mb-1.5">{title}</h3>
                <p className="text-slate-500 text-sm leading-relaxed">{desc}</p>
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
              <span className="text-white text-sm font-medium">Powered by AI — Grounded in Government Data</span>
            </div>
            <h2 className="text-3xl md:text-5xl font-black text-white mb-4">
              Ask anything about<br />Tamil Nadu Government
            </h2>
            <p className="text-blue-200 text-lg mb-8 max-w-xl mx-auto">
              Get instant answers, with sources and verification status, about schemes, services, eligibility criteria, deadlines and more — in English or Tamil.
            </p>
            <Link href="/assistant" className="inline-flex items-center gap-3 bg-white text-brand-700 font-bold px-8 py-4 rounded-2xl hover:bg-blue-50 transition-all shadow-2xl text-lg">
              <MessageSquare size={22} />
              Start Conversation
              <ArrowRight size={20} />
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer className="bg-slate-900 text-slate-400 py-12">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-10">
            <div>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-saffron-400 to-brand-600 flex items-center justify-center">
                  <span className="text-white font-bold text-xs">MG</span>
                </div>
                <span className="text-white font-bold">MyGovt</span>
              </div>
              <p className="text-sm leading-relaxed">
                Your Government. Your Services. Your Voice.<br />
                Tamil Nadu, India.
              </p>
            </div>
            {[
              { title: "Citizen Services", links: ["Find Schemes", "e-Sevai Services", "File Complaint", "Track Complaint"] },
              { title: "Information", links: ["Policy Documents", "Government Orders", "Departments", "Districts"] },
              { title: "Platform", links: ["AI Assistant", "About MyGovt", "Privacy Policy", "Accessibility"] },
            ].map(({ title, links }) => (
              <div key={title}>
                <h4 className="text-white font-semibold mb-3 text-sm">{title}</h4>
                <ul className="space-y-2">
                  {links.map((link) => (
                    <li key={link}>
                      <Link href="#" className="text-sm hover:text-white transition-colors">{link}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <div className="border-t border-slate-800 pt-6 flex flex-col sm:flex-row justify-between items-center gap-4">
            <p className="text-xs">© 2024 Government of Tamil Nadu. All rights reserved.</p>
            <p className="text-xs">Records are labelled by verification status. Provisional items have not yet been verified against an official document; confirm with the department before acting.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
