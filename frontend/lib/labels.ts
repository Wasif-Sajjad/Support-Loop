import type { Decision, Intent, TicketStatus } from "./types";

/**
 * Translates raw API enums and machine identifiers into clear plain language.
 * No raw snake_case or technical enums should appear directly in user-facing UI.
 */

export const intentLabels: Record<Intent, string> = {
  recover_password: "Password Recovery",
  create_account: "Account Creation",
  delete_account: "Account Deletion",
  edit_account: "Account Details Update",
  switch_account: "Account Switch",
  registration_problems: "Sign-Up / Registration Issue",
  contact_human_agent: "Human Agent Request",
  contact_customer_service: "Customer Service Contact",
  complaint: "Customer Complaint",
  infrastructure_issue: "Infrastructure / Kubernetes Issue",
};

export const categoryLabels: Record<string, string> = {
  ACCOUNT: "Account Management",
  CONTACT: "Direct Contact",
  FEEDBACK: "Customer Sentiment",
  INFRA: "Platform Infrastructure",
  BILLING: "Billing & Subscriptions",
};

export const statusLabels: Record<TicketStatus, string> = {
  received: "Ticket Received",
  classified: "Intent Classified",
  retrieved: "Knowledge Retrieved",
  drafted: "Response Drafted",
  resolved: "Auto-Resolved",
  escalated: "Escalated to Human",
  failed: "Processing Error",
};

export const decisionLabels: Record<Decision, string> = {
  auto_resolve: "Auto-Resolved",
  escalate: "Escalated to Human",
};

export function formatIntent(intent: string | null | undefined): string {
  if (!intent) return "Unclassified";
  return intentLabels[intent as Intent] ?? intent.replace(/_/g, " ");
}

export function formatCategory(category: string | null | undefined): string {
  if (!category) return "—";
  return categoryLabels[category.toUpperCase()] ?? category;
}

export function formatStatus(status: TicketStatus | string): string {
  return statusLabels[status as TicketStatus] ?? status;
}

export function formatDecision(decision: Decision | string | null | undefined): string {
  if (!decision) return "Pending Decision";
  return decisionLabels[decision as Decision] ?? decision;
}

export function isPolicyDenylist(intent?: string | null, reason?: string | null): boolean {
  if (intent && (intent === "delete_account" || intent === "complaint")) {
    return true;
  }
  if (reason && reason.toLowerCase().includes("denylist")) {
    return true;
  }
  return false;
}

export function formatConfidence(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatCost(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (value === 0) return "$0.0000";
  return `$${value.toFixed(4)}`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;
}

export function formatDate(dateString?: string | null): string {
  if (!dateString) return "—";
  try {
    const d = new Date(dateString);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  } catch {
    return dateString;
  }
}
