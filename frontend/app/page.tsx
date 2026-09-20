import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-8 max-w-3xl py-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-text-primary">
          Support Loop Operations Console
        </h1>
        <p className="text-text-secondary mt-2 text-sm leading-relaxed">
          Autonomous IT & customer support ticket triage pipeline. Every ticket is classified,
          grounded against verified knowledge passages, and audited by an entailment critic
          before any automated resolution is dispatched.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Link
          href="/submit"
          className="p-4 rounded border border-border bg-surface hover:bg-surface-raised hover:border-resolve/50 transition-colors group"
        >
          <div className="text-xs font-mono text-resolve mb-1">01 / INGRESS</div>
          <div className="text-sm font-semibold text-text-primary group-hover:text-resolve">
            Submit & Test &rarr;
          </div>
          <div className="text-xs text-text-secondary mt-1">
            Trigger real-time ticket triage with scenario presets.
          </div>
        </Link>

        <Link
          href="/queue"
          className="p-4 rounded border border-border bg-surface hover:bg-surface-raised hover:border-escalate/50 transition-colors group"
        >
          <div className="text-xs font-mono text-escalate mb-1">02 / OPERATOR QUEUE</div>
          <div className="text-sm font-semibold text-text-primary group-hover:text-escalate">
            Escalation Queue &rarr;
          </div>
          <div className="text-xs text-text-secondary mt-1">
            Review tickets held by policy denylists or citation gaps.
          </div>
        </Link>

        <Link
          href="/dashboard"
          className="p-4 rounded border border-border bg-surface hover:bg-surface-raised hover:border-text-primary/50 transition-colors group"
        >
          <div className="text-xs font-mono text-text-secondary mb-1">03 / TELEMETRY</div>
          <div className="text-sm font-semibold text-text-primary group-hover:text-text-primary">
            Metrics Dashboard &rarr;
          </div>
          <div className="text-xs text-text-secondary mt-1">
            Track resolution ratio, token costs, and pipeline latency.
          </div>
        </Link>
      </div>
    </div>
  );
}
