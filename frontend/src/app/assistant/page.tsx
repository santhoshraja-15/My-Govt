"use client";

import { useState, useRef, useEffect } from "react";
import {
  Send, Bot, User, AlertTriangle, ExternalLink,
  Info, Loader2, MessageSquare, RefreshCw, ChevronDown
} from "lucide-react";
import { chat as chatAPI } from "@/lib/api";
import type { Metadata } from "next";

interface Citation {
  index: number;
  title: string;
  department?: string;
  source_url?: string;
  verified_at?: string;
  verification_status?: string;
  page?: number | null;
  excerpt?: string | null;
  outdated?: boolean;
  chunk_id?: string | null;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  trust_score?: number;
  abstained?: boolean;
  abstain_reason?: string;
  degraded?: boolean;
  intent?: string;
  suggested_actions?: string[];
  contains_unverified?: boolean;
  evidence_notes?: string[];
}

const SUGGESTED_QUESTIONS = [
  "What schemes are available for BPL women in Tamil Nadu?",
  "Am I eligible for the CM Health Insurance scheme?",
  "How do I apply for a community certificate?",
  "What is the Kalaignar Magalir Urimai scheme?",
  "How to track my complaint status?",
  "What benefits do disabled persons get?",
];

function TrustIndicator({ score }: { score?: number }) {
  if (score === undefined) return null;
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? "text-emerald-600" : pct >= 60 ? "text-amber-500" : "text-rose-500";
  const bg   = pct >= 80 ? "bg-emerald-100" : pct >= 60 ? "bg-amber-100" : "bg-rose-100";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${bg} ${color}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {pct}% trust
    </span>
  );
}

function CitationCard({ citations }: { citations: Citation[] }) {
  if (!citations?.length) return null;
  return (
    <div className="mt-3 pt-3 border-t border-slate-100">
      <p className="text-xs font-semibold text-slate-500 mb-2 flex items-center gap-1">
        <ExternalLink size={12} /> Sources
      </p>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c) => (
          <a key={c.index} href={c.source_url || "#"} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs bg-brand-50 text-brand-700 hover:bg-brand-100 px-2.5 py-1 rounded-full border border-brand-100 transition-all">
            [{c.index}] {c.title}{c.page ? ` · p.${c.page}` : ""}
            {c.outdated && <span className="text-[10px] uppercase tracking-wide text-red-700">outdated</span>}
            {c.verification_status && c.verification_status !== "official_verified" && (
              <span className="text-[10px] uppercase tracking-wide text-amber-700">{c.verification_status.replace("_", " ")}</span>
            )}
            {c.source_url && <ExternalLink size={10} />}
          </a>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"} animate-slide-up`}>
      {!isUser && (
        <div className="shrink-0 w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-teal-600 flex items-center justify-center">
          <Bot size={16} className="text-white" />
        </div>
      )}

      <div className={`max-w-[80%] ${isUser ? "items-end" : "items-start"} flex flex-col gap-1`}>
        {isUser ? (
          <div className="chat-bubble-user text-sm leading-relaxed">{msg.content}</div>
        ) : (
          <div className="chat-bubble-assistant">
            {msg.abstained && (
              <div className="flex items-start gap-2 mb-3 p-2.5 bg-amber-50 rounded-xl border border-amber-200">
                <AlertTriangle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                <p className="text-xs text-amber-700">
                  I couldn&apos;t find sufficiently verified information to answer this confidently.
                </p>
              </div>
            )}

            {msg.degraded && (
              <div className="flex items-center gap-1.5 mb-2 text-xs text-slate-500">
                <Info size={12} />
                <span>AI model unavailable — responding from database</span>
              </div>
            )}

            {msg.contains_unverified && (
              <div role="note" data-testid="unverified-notice" className="mb-2 text-xs bg-amber-50 border border-amber-200 text-amber-800 rounded-lg px-2.5 py-1.5">
                Some of the sources below are provisional or external and have not been verified against an official document. Please confirm with the department.
              </div>
            )}
            <p className="text-sm text-slate-800 leading-relaxed whitespace-pre-wrap" data-testid="assistant-answer">{msg.content}</p>
            {msg.evidence_notes?.length ? (
              <ul data-testid="evidence-notes" className="mt-2 text-xs text-slate-500 list-disc pl-4 space-y-0.5">
                {msg.evidence_notes.map((n) => <li key={n}>{n}</li>)}
              </ul>
            ) : null}

            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <TrustIndicator score={msg.trust_score} />
              {msg.intent && (
                <span className="badge badge-slate text-xs">{msg.intent.replace("_", " ")}</span>
              )}
            </div>

            <CitationCard citations={msg.citations || []} />

            {msg.suggested_actions?.length ? (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {msg.suggested_actions.map((action) => (
                  <button key={action}
                    className="text-xs bg-slate-50 hover:bg-brand-50 text-slate-600 hover:text-brand-700 px-3 py-1.5 rounded-full border border-slate-200 hover:border-brand-200 transition-all">
                    {action}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {isUser && (
        <div className="shrink-0 w-8 h-8 rounded-xl bg-slate-200 flex items-center justify-center">
          <User size={16} className="text-slate-600" />
        </div>
      )}
    </div>
  );
}

export default function AssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;
    setInput("");

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: msg };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await chatAPI.send(msg, conversationId);
      setConversationId(res.conversation_id);
      const assistantMsg: Message = {
        id: res.message_id,
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        trust_score: res.trust_score,
        abstained: res.abstained,
        abstain_reason: res.abstain_reason,
        degraded: res.degraded,
        intent: res.intent,
        suggested_actions: res.suggested_actions,
        contains_unverified: res.contains_unverified,
        evidence_notes: res.evidence_notes,
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "I'm having trouble connecting to the server. Please try again.",
          abstained: true,
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const startNew = () => {
    setMessages([]);
    setConversationId(undefined);
    setInput("");
    inputRef.current?.focus();
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-30">
        <div className="max-w-4xl mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-600 to-teal-600 flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-slate-900 text-sm">MyGovt AI Assistant</h1>
              <p className="text-xs text-slate-500">Grounded answers from official Tamil Nadu government data</p>
            </div>
          </div>
          <button onClick={startNew}
            className="btn-ghost text-slate-500 text-xs flex items-center gap-1.5">
            <RefreshCw size={14} /> New Chat
          </button>
        </div>
      </header>

      {/* Messages area */}
      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-6 flex flex-col">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-8 animate-fade-in">
            <div className="text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-600 to-teal-600 flex items-center justify-center mx-auto mb-4 shadow-xl">
                <MessageSquare size={28} className="text-white" />
              </div>
              <h2 className="text-2xl font-bold text-slate-900 mb-2">How can I help you?</h2>
              <p className="text-slate-500 text-sm max-w-sm">
                Ask about government schemes, eligibility, services, complaints or any Tamil Nadu government information.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button key={q} onClick={() => sendMessage(q)}
                  className="card p-4 text-left text-sm text-slate-700 hover:border-brand-200 hover:text-brand-700 transition-all">
                  <ChevronDown size={14} className="text-slate-300 mb-1 rotate-[-90deg]" />
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col gap-6">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} msg={msg} />
            ))}
            {loading && (
              <div className="flex gap-3 items-start animate-fade-in">
                <div className="shrink-0 w-8 h-8 rounded-xl bg-gradient-to-br from-brand-600 to-teal-600 flex items-center justify-center">
                  <Bot size={16} className="text-white" />
                </div>
                <div className="chat-bubble-assistant">
                  <div className="flex items-center gap-2 text-slate-500 text-sm">
                    <Loader2 size={14} className="animate-spin" />
                    Searching government data…
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </main>

      {/* Input */}
      <div className="sticky bottom-0 bg-white border-t border-slate-200 py-4">
        <div className="max-w-4xl mx-auto px-4">
          <div className="flex gap-3 items-end">
            <textarea
              ref={inputRef}
              aria-label="Ask a question"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about Tamil Nadu government schemes, services, or complaints…"
              rows={1}
              className="input resize-none flex-1 py-3 max-h-32"
              style={{ height: "auto" }}
              onInput={(e) => {
                const t = e.target as HTMLTextAreaElement;
                t.style.height = "auto";
                t.style.height = Math.min(t.scrollHeight, 128) + "px";
              }}
              disabled={loading}
            />
            <button onClick={() => sendMessage()} disabled={loading || !input.trim()} aria-label="Send message"
              className="btn-primary h-11 w-11 p-0 justify-center rounded-xl shrink-0 disabled:opacity-40">
              {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-2 text-center">
            Answers are grounded in official Tamil Nadu government sources. Not a substitute for official advice.
          </p>
        </div>
      </div>
    </div>
  );
}
