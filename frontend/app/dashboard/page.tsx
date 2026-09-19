"use client";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_URL}/metrics/summary`)
      .then((r) => r.json())
      .then(setMetrics)
      .catch(() => setMetrics(null));
  }, []);

  return (
    <div>
      <h1 className="text-xl font-semibold mb-4">Metrics Dashboard</h1>
      {!metrics ? (
        <p className="text-gray-500">No data yet — submit some tickets first.</p>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <Metric label="Total tickets" value={metrics.total_tickets} />
          <Metric label="Resolution rate" value={`${(metrics.resolution_rate * 100).toFixed(1)}%`} />
          <Metric label="Escalation rate" value={`${(metrics.escalation_rate * 100).toFixed(1)}%`} />
          <Metric label="Avg cost/ticket" value={metrics.avg_cost_usd ?? "—"} />
        </div>
      )}
      {/* TODO (Epic I3): replace with real Recharts charts over time, not just current totals */}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-white border rounded p-4">
      <div className="text-gray-500 text-sm">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
