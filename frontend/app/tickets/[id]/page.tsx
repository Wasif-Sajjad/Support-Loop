"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getTicket, getTicketTrace } from "@/lib/api";
import { formatIntent, isPolicyDenylist, formatDate } from "@/lib/labels";
import type { TicketResponse, TicketTrace } from "@/lib/types";
import DecisionBadge from "@/components/DecisionBadge";
import TraceTimeline from "@/components/TraceTimeline";

export default function TicketDetailPage() {
  const params = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<TicketResponse | null>(null);
  const [trace, setTrace] = useState<TicketTrace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;
    setLoading(true);
    Promise.all([getTicket(params.id), getTicketTrace(params.id)])
      .then(([t, tr]) => {
        setTicket(t);
        setTrace(tr);
        setError(null);
      })
      .catch((err) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load ticket reasoning trace."
        );
      })
      .finally(() => {
        setLoading(false);
      });
  }, [params.id]);

  if (loading) {
    return (
      <div className="py-12">
        <div className="flex items-center gap-2 font-mono text-xs text-text-secondary">
          <span className="w-2 h-2 rounded-full bg-text-secondary/50 animate-pulse" />
          Loading ticket trace data…
        </div>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-2xl py-8">
        <div className="rounded border border-denylist/40 bg-denylist-dim/40 p-4 text-xs">
          <div className="font-semibold text-denylist mb-1">
            Trace Retrieval Error
          </div>
          <p className="text-text-secondary">{error || "Ticket not found."}</p>
        </div>
        <div className="mt-4">
          <Link
            href="/queue"
            className="text-xs font-mono text-text-secondary hover:text-text-primary underline underline-offset-4"
          >
            &larr; Return to Escalation Queue
          </Link>
        </div>
      </div>
    );
  }

  const isDenylist = isPolicyDenylist(
    ticket.intent,
    trace?.critic_reason
  );

  return (
    <div className="space-y-6">
      {/* Breadcrumb / Top metadata bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-text-secondary font-mono">
          <Link
            href="/queue"
            className="hover:text-text-primary transition-colors"
          >
            Queue
          </Link>
          <span>/</span>
          <span className="text-text-primary">{ticket.id.slice(0, 8)}</span>
        </div>
        <div className="font-mono text-[11px] text-text-secondary">
          {formatDate(ticket.created_at)}
        </div>
      </div>

      {/* Main Ticket Header */}
      <div className="rounded border border-border bg-surface p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight text-text-primary">
              {formatIntent(ticket.intent)}
            </h1>
            <div className="font-mono text-xs text-text-secondary mt-1">
              UUID: {ticket.id}
            </div>
          </div>
          <DecisionBadge
            decision={ticket.decision}
            policyDenylist={isDenylist}
            size="md"
          />
        </div>

        {/* Submitted Raw Text */}
        <div className="mt-4 pt-4 border-t border-border/60">
          <div className="text-xs font-medium text-text-secondary mb-1.5 uppercase tracking-wider">
            User Submitted Text
          </div>
          <div className="p-3 rounded bg-surface-raised border border-border text-text-primary text-xs font-mono leading-relaxed whitespace-pre-wrap">
            {ticket.raw_text || trace?.ticket_text || "—"}
          </div>
        </div>

        {/* Final Decision Output Banner */}
        <div className="mt-4">
          {ticket.decision === "auto_resolve" ? (
            <div className="rounded border border-resolve/30 bg-resolve-dim/30 p-4 text-xs">
              <div className="font-semibold text-resolve mb-1 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-resolve" />
                Auto-Resolved Resolution
              </div>
              <p className="text-text-primary leading-relaxed whitespace-pre-wrap">
                {ticket.final_answer || trace?.final_answer || "Resolution provided to user."}
              </p>
            </div>
          ) : (
            <div
              className={`rounded border p-4 text-xs ${
                isDenylist
                  ? "border-denylist/30 bg-denylist-dim/30"
                  : "border-escalate/30 bg-escalate-dim/30"
              }`}
            >
              <div
                className={`font-semibold mb-1 flex items-center gap-1.5 ${
                  isDenylist ? "text-denylist" : "text-escalate"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isDenylist ? "bg-denylist" : "bg-escalate"
                  }`}
                />
                {isDenylist
                  ? "Policy Denylist Escalation — Human Action Required"
                  : "Confidence / Citation Escalation — Human Action Required"}
              </div>
              <p className="text-text-secondary leading-relaxed">
                {trace?.critic_reason ||
                  "The triage agent determined this ticket requires direct review by a support engineer."}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Sequential Reasoning Trace Section */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold tracking-tight text-text-primary">
              Sequential Reasoning Trace
            </h2>
            <p className="text-xs text-text-secondary mt-0.5">
              4-stage verification pipeline executed by the autonomous triage agent.
            </p>
          </div>
        </div>

        {trace ? (
          <TraceTimeline trace={trace} />
        ) : (
          <div className="rounded border border-border bg-surface p-6 text-xs text-text-secondary italic">
            Trace records could not be reconstructed for this ticket.
          </div>
        )}
      </div>
    </div>
  );
}
