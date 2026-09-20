/**
 * Types mirroring the backend Pydantic schemas (backend/app/schemas.py) and
 * API responses.
 */

export type Decision = "auto_resolve" | "escalate";

export type TicketStatus =
  | "received"
  | "classified"
  | "retrieved"
  | "drafted"
  | "resolved"
  | "escalated"
  | "failed";

export type Intent =
  | "recover_password"
  | "create_account"
  | "delete_account"
  | "edit_account"
  | "switch_account"
  | "registration_problems"
  | "contact_human_agent"
  | "contact_customer_service"
  | "complaint"
  | "infrastructure_issue";

export interface TicketCreate {
  raw_text: string;
  channel?: string;
}

export interface TicketResponse {
  id: string;
  raw_text?: string;
  status: TicketStatus;
  intent: string | null;
  category: string | null;
  classifier_confidence?: number | null;
  final_answer: string | null;
  cited_chunk_ids?: string[];
  decision: Decision | null;
  created_at?: string;
}

/** Entailment result for one cited chunk produced by the critic (E1). */
export interface EntailmentStepTrace {
  chunk_id: string;
  chunk_content_preview: string;
  supported: boolean;
  reason: string;
}

/** Full E4 per-ticket reasoning trace reconstructed from the database. */
export interface TicketTrace {
  ticket_id: string;
  ticket_text: string;

  // 1. Classifier step
  intent: string;
  category: string;
  classifier_confidence: number;

  // 2. Retriever & Cache step
  retrieved_chunk_ids: string[];
  retrieved_chunk_count: number;
  cache_hit: boolean;
  cached_answer: string | null;

  // 3. Drafter step
  draft_answer: string;
  draft_cited_chunk_ids: string[];
  draft_confidence: number;

  // 4. Critic step
  threshold_used: number;
  entailment_steps: EntailmentStepTrace[];
  citation_supported: boolean;
  critic_reason: string;

  // Final decision
  decision: Decision;
  final_answer: string | null;
}

export interface MetricsSummary {
  total_tickets: number;
  resolution_rate: number;
  escalation_rate: number;
  avg_cost_usd: number | null;
  avg_latency_ms: number | null;
}

/** Narrow, typed error shape for failed API calls. */
export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
