"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMetricsSummary, listTickets } from "@/lib/api";
import {
  formatCost,
  formatLatency,
  formatIntent,
  formatCategory,
  isPolicyDenylist,
  formatDate,
} from "@/lib/labels";
import type { MetricsSummary, TicketResponse } from "@/lib/types";
import DecisionBadge from "@/components/DecisionBadge";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [recentTickets, setRecentTickets] = useState<TicketResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([getMetricsSummary(), listTickets()])
      .then(([m, t]) => {
        setMetrics(m);
        setRecentTickets(t.slice(0, 10));
        setError(null);
      })
      .catch(() => {
        setError("Failed to load telemetry summary.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text-primary">
          Metrics & Telemetry
        </h1>
        <p className="text-xs text-text-secondary mt-1">
          Real-time triage resolution ratio, latency, and cost telemetry.
        </p>
      </div>

      {error && (
        <div className="rounded border border-denylist/40 bg-denylist-dim/40 p-4 text-xs text-text-primary">
          <div className="font-semibold text-denylist mb-1">Telemetry Error</div>
          <p className="text-text-secondary">{error}</p>
        </div>
      )}

      {loading && !metrics && (
        <div className="rounded border border-border bg-surface p-8 text-center text-xs font-mono text-text-secondary">
          Loading metrics data…
        </div>
      )}

      {metrics && (
        <>
          {/* Key Performance Indicators Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Tickets */}
            <div className="rounded border border-border bg-surface p-4">
              <div className="text-xs font-medium text-text-secondary mb-1">
                Total Tickets Processed
              </div>
              <div className="text-2xl font-mono font-semibold text-text-primary">
                {metrics.total_tickets}
              </div>
              <div className="text-[11px] font-mono text-text-secondary mt-1">
                All ingress channels
              </div>
            </div>

            {/* Auto-Resolution Rate */}
            <div className="rounded border border-resolve/30 bg-surface p-4">
              <div className="text-xs font-medium text-text-secondary mb-1">
                Auto-Resolution Rate
              </div>
              <div className="text-2xl font-mono font-semibold text-resolve">
                {(metrics.resolution_rate * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] font-mono text-text-secondary mt-1">
                Passed confidence & citation audit
              </div>
            </div>

            {/* Escalation Rate */}
            <div className="rounded border border-escalate/30 bg-surface p-4">
              <div className="text-xs font-medium text-text-secondary mb-1">
                Escalation Rate
              </div>
              <div className="text-2xl font-mono font-semibold text-escalate">
                {(metrics.escalation_rate * 100).toFixed(1)}%
              </div>
              <div className="text-[11px] font-mono text-text-secondary mt-1">
                Routed to human queue
              </div>
            </div>

            {/* Average Latency & Cost */}
            <div className="rounded border border-border bg-surface p-4">
              <div className="text-xs font-medium text-text-secondary mb-1">
                Average Latency / Cost
              </div>
              <div className="text-2xl font-mono font-semibold text-text-primary">
                {formatLatency(metrics.avg_latency_ms)}
              </div>
              <div className="text-[11px] font-mono text-text-secondary mt-1">
                Avg cost: {formatCost(metrics.avg_cost_usd)}
              </div>
            </div>
          </div>

          {/* Recent Ingress Traffic */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold tracking-tight text-text-primary">
                Recent Triage Stream
              </h2>
              <span className="font-mono text-xs text-text-secondary">
                Last {recentTickets.length} tickets
              </span>
            </div>

            {recentTickets.length === 0 ? (
              <div className="rounded border border-border bg-surface p-8 text-center text-xs text-text-secondary">
                No tickets have been triaged yet. Submit a test ticket to generate traffic.
              </div>
            ) : (
              <div className="rounded border border-border bg-surface overflow-hidden">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="bg-surface-raised text-text-secondary border-b border-border text-[11px] font-normal">
                      <th className="py-2.5 px-4 font-normal">ID</th>
                      <th className="py-2.5 px-4 font-normal">Intent</th>
                      <th className="py-2.5 px-4 font-normal">Category</th>
                      <th className="py-2.5 px-4 font-normal">Verdict</th>
                      <th className="py-2.5 px-4 font-normal">Timestamp</th>
                      <th className="py-2.5 px-4 font-normal text-right">Trace</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {recentTickets.map((t) => (
                      <tr
                        key={t.id}
                        className="hover:bg-surface-raised/40 transition-colors"
                      >
                        <td className="py-2.5 px-4 font-mono text-text-secondary">
                          {t.id.slice(0, 8)}
                        </td>
                        <td className="py-2.5 px-4 font-medium text-text-primary">
                          {formatIntent(t.intent)}
                        </td>
                        <td className="py-2.5 px-4 text-text-secondary">
                          {formatCategory(t.category)}
                        </td>
                        <td className="py-2.5 px-4">
                          <DecisionBadge
                            decision={t.decision}
                            policyDenylist={isPolicyDenylist(t.intent)}
                            size="sm"
                          />
                        </td>
                        <td className="py-2.5 px-4 font-mono text-[11px] text-text-secondary">
                          {formatDate(t.created_at)}
                        </td>
                        <td className="py-2.5 px-4 text-right">
                          <Link
                            href={`/tickets/${t.id}`}
                            className="font-mono text-resolve hover:underline font-medium"
                          >
                            Trace &rarr;
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
