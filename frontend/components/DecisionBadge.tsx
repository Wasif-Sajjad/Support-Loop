import type { Decision } from "@/lib/types";

interface DecisionBadgeProps {
  decision: Decision | string | null | undefined;
  policyDenylist?: boolean;
  size?: "sm" | "md";
}

export default function DecisionBadge({
  decision,
  policyDenylist = false,
  size = "md",
}: DecisionBadgeProps) {
  const isSmall = size === "sm";
  const sizeClasses = isSmall
    ? "px-2 py-0.5 text-xs"
    : "px-2.5 py-1 text-xs font-medium";

  if (!decision) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded border border-border bg-surface-raised text-text-secondary ${sizeClasses}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-text-secondary/60 shrink-0" />
        Pending Decision
      </span>
    );
  }

  if (decision === "auto_resolve") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded border border-resolve/40 bg-resolve-dim/50 text-resolve ${sizeClasses}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-resolve shrink-0" />
        Auto-Resolved
      </span>
    );
  }

  if (policyDenylist) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded border border-denylist/40 bg-denylist-dim/50 text-denylist ${sizeClasses}`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-denylist shrink-0" />
        Policy Escalation
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border border-escalate/40 bg-escalate-dim/50 text-escalate ${sizeClasses}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-escalate shrink-0" />
      Escalated to Human
    </span>
  );
}
