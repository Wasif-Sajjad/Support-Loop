"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { createTicket, getTicket } from "@/lib/api";
import { formatIntent, formatCategory, isPolicyDenylist } from "@/lib/labels";
import type { TicketResponse } from "@/lib/types";
import { ApiError } from "@/lib/types";
import DecisionBadge from "@/components/DecisionBadge";

const PRESETS = [
  {
    label: "Password Recovery",
    path: "Auto-Resolve",
    text: "I forgot my account password and need to reset it. Can you tell me how to recover access?",
  },
  {
    label: "Infrastructure Issue",
    path: "High-Threshold (0.90)",
    text: "Our kubernetes pod keeps throwing CrashLoopBackOff after the deploy. How do I inspect events?",
  },
  {
    label: "Delete Account",
    path: "Policy Denylist",
    text: "Please permanently delete my account and wipe all stored data immediately.",
  },
  {
    label: "Customer Complaint",
    path: "Policy Denylist",
    text: "I am extremely unsatisfied with the support response time and wish to log a formal complaint.",
  },
];

export default function SubmitPage() {
  const [text, setText] = useState("");
  const [ticket, setTicket] = useState<TicketResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollStage, setPollStage] = useState<string>("Enqueued");
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    };
  }, []);

  async function pollTicketStatus(ticketId: string, attempts = 0) {
    if (attempts > 60) {
      setError("Ticket execution timed out. Please check the queue or try again.");
      setLoading(false);
      return;
    }

    try {
      const current = await getTicket(ticketId);
      if (current.status === "resolved" || current.status === "escalated") {
        setTicket(current);
        setLoading(false);
        return;
      }
      if (current.status === "failed") {
        setError("Autonomous triage pipeline failed during execution.");
        setLoading(false);
        return;
      }

      // Update in-progress animation stage
      if (attempts === 0) setPollStage("Enqueued to ARQ Task Queue");
      else if (attempts === 1) setPollStage("Running Intent Classification & Retrieval");
      else if (attempts >= 2) setPollStage("Executing Drafting & Entailment Critic");

      pollTimerRef.current = setTimeout(() => {
        pollTicketStatus(ticketId, attempts + 1);
      }, 1200);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to poll ticket status."
      );
      setLoading(false);
    }
  }

  async function handleSubmit(e?: React.FormEvent) {
    if (e) e.preventDefault();
    if (!text.trim() || loading) return;

    if (pollTimerRef.current) clearTimeout(pollTimerRef.current);
    setLoading(true);
    setError(null);
    setTicket(null);
    setPollStage("Enqueued to ARQ Task Queue");

    try {
      const initialTicket = await createTicket({ raw_text: text });
      if (initialTicket.status === "resolved" || initialTicket.status === "escalated") {
        setTicket(initialTicket);
        setLoading(false);
      } else {
        // Asynchronous processing: start polling loop
        pollTimerRef.current = setTimeout(() => {
          pollTicketStatus(initialTicket.id, 0);
        }, 800);
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to submit ticket."
      );
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text-primary">
          Submit & Test Ticket
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Simulate an incoming support ticket and inspect how the autonomous agent
          classifies, grounds, and audits its triage decision.
        </p>
      </div>

      {/* Preset scenarios for fast ops evaluation */}
      <div className="rounded border border-border bg-surface p-4">
        <div className="text-[11px] font-medium text-text-secondary mb-2 uppercase tracking-wider">
          Test Scenarios
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => {
                setText(preset.text);
                setTicket(null);
                setError(null);
              }}
              className="text-left p-2.5 rounded border border-border bg-surface-raised/60 hover:bg-surface-raised hover:border-border transition-colors text-xs group"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-text-primary group-hover:text-text-primary">
                  {preset.label}
                </span>
                <span className="font-mono text-[10px] text-text-secondary">
                  {preset.path}
                </span>
              </div>
              <div className="text-[11px] text-text-secondary/70 truncate mt-1">
                {preset.text}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Submission Form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label
            htmlFor="ticket_text"
            className="block text-xs font-medium text-text-secondary mb-1.5"
          >
            Raw Ticket Text
          </label>
          <textarea
            id="ticket_text"
            rows={5}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type ticket body or select a preset scenario above…"
            className="w-full rounded border border-border bg-surface px-3.5 py-3 text-xs text-text-primary font-mono placeholder:font-sans placeholder:text-text-secondary/50 focus:border-border focus:ring-1 focus:ring-border outline-none resize-none leading-relaxed"
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          <span className="font-mono text-[11px] text-text-secondary">
            {text.length} characters
          </span>
          <button
            type="submit"
            disabled={loading || !text.trim()}
            className="rounded border border-resolve/60 bg-resolve text-base px-4 py-2 text-xs font-semibold hover:bg-resolve/90 disabled:opacity-30 disabled:cursor-not-allowed transition-all font-sans"
          >
            {loading ? "Executing Pipeline…" : "Execute Triage Pipeline"}
          </button>
        </div>
      </form>

      {/* Loading state indicator */}
      {loading && (
        <div className="rounded border border-border bg-surface p-5 text-xs text-text-secondary space-y-2">
          <div className="flex items-center gap-2 font-mono">
            <span className="w-2 h-2 rounded-full bg-resolve animate-ping" />
            <span className="text-text-primary font-medium">{pollStage}…</span>
          </div>
          <p className="text-[11px] text-text-secondary/70">
            Async worker pipeline: Classification &rarr; Knowledge Retrieval &rarr; Resolution Drafting &rarr; Entailment Critic.
          </p>
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded border border-denylist/40 bg-denylist-dim/40 p-4 text-xs text-text-primary">
          <div className="font-semibold text-denylist mb-1">Execution Failure</div>
          <p className="text-text-secondary">{error}</p>
        </div>
      )}

      {/* Triage Decision Output Card */}
      {ticket && !loading && (
        <div className="rounded border border-border bg-surface p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 pb-3 border-b border-border/60">
            <div>
              <div className="text-sm font-bold text-text-primary">
                {formatIntent(ticket.intent)}
              </div>
              <div className="font-mono text-[11px] text-text-secondary mt-0.5">
                Category: {formatCategory(ticket.category)} | ID: {ticket.id.slice(0, 8)}…
              </div>
            </div>
            <DecisionBadge
              decision={ticket.decision}
              policyDenylist={isPolicyDenylist(ticket.intent)}
              size="md"
            />
          </div>

          <div>
            <div className="text-xs font-medium text-text-secondary mb-1 uppercase tracking-wider">
              {ticket.decision === "auto_resolve"
                ? "Auto-Generated Resolution"
                : "Escalation Action"}
            </div>
            <div className="p-3.5 rounded bg-surface-raised border border-border text-xs leading-relaxed text-text-primary whitespace-pre-wrap">
              {ticket.final_answer ? (
                ticket.final_answer
              ) : (
                <span className="text-text-secondary italic">
                  Ticket flagged for human triage. No resolution delivered directly to the user.
                </span>
              )}
            </div>
          </div>

          <div className="pt-1 flex items-center justify-between text-xs">
            <span className="font-mono text-[11px] text-text-secondary">
              Status: {ticket.status}
            </span>
            <Link
              href={`/tickets/${ticket.id}`}
              className="inline-flex items-center gap-1.5 font-semibold text-resolve hover:underline underline-offset-4"
            >
              Inspect 4-Stage Reasoning Trace &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
