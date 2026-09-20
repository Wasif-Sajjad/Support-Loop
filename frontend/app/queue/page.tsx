"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { listTickets } from "@/lib/api";
import {
  formatIntent,
  formatCategory,
  isPolicyDenylist,
  formatDate,
} from "@/lib/labels";
import type { TicketResponse } from "@/lib/types";
import DecisionBadge from "@/components/DecisionBadge";

type FilterType = "all" | "policy" | "confidence";

export default function QueuePage() {
  const [tickets, setTickets] = useState<TicketResponse[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");

  function loadQueue() {
    setLoading(true);
    setError(null);
    listTickets("escalate")
      .then((data) => {
        setTickets(data);
        setError(null);
      })
      .catch(() => {
        setError("Failed to fetch tickets from the escalation queue.");
      })
      .finally(() => {
        setLoading(false);
      });
  }

  useEffect(() => {
    loadQueue();
  }, []);

  const filteredTickets = useMemo(() => {
    if (!tickets) return [];
    if (filter === "policy") {
      return tickets.filter((t) => isPolicyDenylist(t.intent));
    }
    if (filter === "confidence") {
      return tickets.filter((t) => !isPolicyDenylist(t.intent));
    }
    return tickets;
  }, [tickets, filter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">
            Escalation Queue
          </h1>
          <p className="text-xs text-text-secondary mt-1">
            Tickets requiring human operator intervention, categorized by guardrail failure type.
          </p>
        </div>
        <button
          type="button"
          onClick={loadQueue}
          disabled={loading}
          className="rounded border border-border bg-surface px-3 py-1.5 text-xs font-mono text-text-secondary hover:text-text-primary hover:bg-surface-raised transition-colors disabled:opacity-50"
        >
          {loading ? "Refreshing…" : "Refresh Queue"}
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 border-b border-border pb-2 text-xs font-medium">
        <button
          type="button"
          onClick={() => setFilter("all")}
          className={`px-3 py-1.5 rounded transition-colors ${
            filter === "all"
              ? "bg-surface-raised text-text-primary border border-border"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          All Escalated ({tickets?.length ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setFilter("policy")}
          className={`px-3 py-1.5 rounded transition-colors ${
            filter === "policy"
              ? "bg-surface-raised text-denylist border border-denylist/30"
              : "text-text-secondary hover:text-denylist"
          }`}
        >
          Policy Denylist ({tickets?.filter((t) => isPolicyDenylist(t.intent)).length ?? 0})
        </button>
        <button
          type="button"
          onClick={() => setFilter("confidence")}
          className={`px-3 py-1.5 rounded transition-colors ${
            filter === "confidence"
              ? "bg-surface-raised text-escalate border border-escalate/30"
              : "text-text-secondary hover:text-escalate"
          }`}
        >
          Low Confidence / Citation ({tickets?.filter((t) => !isPolicyDenylist(t.intent)).length ?? 0})
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded border border-denylist/40 bg-denylist-dim/40 p-4 text-xs text-text-primary">
          <div className="font-semibold text-denylist mb-1">Queue Error</div>
          <p className="text-text-secondary">{error}</p>
        </div>
      )}

      {/* Loading state */}
      {loading && !tickets && (
        <div className="rounded border border-border bg-surface p-8 text-center text-xs font-mono text-text-secondary">
          Loading escalated queue records…
        </div>
      )}

      {/* Empty state */}
      {!loading && tickets && filteredTickets.length === 0 && (
        <div className="rounded border border-border bg-surface p-12 text-center text-xs text-text-secondary">
          <div className="font-mono text-text-primary mb-1">Queue Clear</div>
          <p>No tickets currently match this escalation filter.</p>
        </div>
      )}

      {/* Queue Table */}
      {filteredTickets.length > 0 && (
        <div className="rounded border border-border bg-surface overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-surface-raised text-text-secondary border-b border-border text-[11px] font-normal">
                <th className="py-2.5 px-4 font-normal">Ticket ID</th>
                <th className="py-2.5 px-4 font-normal">Intent</th>
                <th className="py-2.5 px-4 font-normal">Category</th>
                <th className="py-2.5 px-4 font-normal">Escalation Trigger</th>
                <th className="py-2.5 px-4 font-normal">Created</th>
                <th className="py-2.5 px-4 font-normal text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredTickets.map((t) => {
                const policy = isPolicyDenylist(t.intent);
                return (
                  <tr
                    key={t.id}
                    className="hover:bg-surface-raised/40 transition-colors"
                  >
                    <td className="py-3 px-4 font-mono text-text-secondary">
                      {t.id.slice(0, 8)}
                    </td>
                    <td className="py-3 px-4 font-medium text-text-primary">
                      {formatIntent(t.intent)}
                    </td>
                    <td className="py-3 px-4 text-text-secondary">
                      {formatCategory(t.category)}
                    </td>
                    <td className="py-3 px-4">
                      <DecisionBadge
                        decision={t.decision}
                        policyDenylist={policy}
                        size="sm"
                      />
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-text-secondary">
                      {formatDate(t.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <Link
                        href={`/tickets/${t.id}`}
                        className="font-mono text-resolve hover:underline underline-offset-4 font-medium"
                      >
                        Inspect &rarr;
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
