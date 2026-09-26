"""Pydantic schemas — the structured-output contracts every agent must honor.
Per AGENTS.md: no agent may return free text as a final output; everything goes
through one of these models first.
"""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    raw_text: str = Field(..., min_length=1)
    channel: str = "api"


class ClassificationResult(BaseModel):
    intent: str
    category: str
    confidence: float = Field(..., ge=0, le=1)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider_name: str = "unknown"


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    content: str
    similarity: float


class DraftResolution(BaseModel):
    answer: str
    cited_chunk_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider_name: str = "unknown"


class CriticVerdict(BaseModel):
    decision: str  # "auto_resolve" | "escalate"
    reason: str
    citation_supported: bool


class CriticVerdictWithTrace(BaseModel):
    """Extended return from escalation_critic that includes per-chunk entailment results.

    Separating this from CriticVerdict keeps the DB schema clean while still giving
    graph.py everything it needs to persist EntailmentTrace rows and assemble the
    full TicketTrace.entailment_steps list.
    """

    verdict: CriticVerdict
    # One (chunk, result) pair per cited chunk that was entailment-checked.
    # Empty if the critic short-circuited before reaching the entailment step
    # (e.g. denylist or confidence-floor escalation).
    entailment_results: list[tuple["RetrievedChunk", "EntailmentResult"]] = []


class EntailmentResult(BaseModel):
    """Structured output from the E1 citation entailment check.

    The LLM is asked: does this KB passage actually support the claim in the
    drafted answer? Returns a boolean decision and a brief human-readable reason
    (used in the reasoning trace).
    """

    supported: bool
    reason: str  # ≤ 2 sentences, used in the E4 reasoning trace
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    provider_name: str = "unknown"


class SingleChunkEntailment(BaseModel):
    chunk_id: str
    supported: bool
    reason: str


class BatchEntailmentResponse(BaseModel):
    results: list[SingleChunkEntailment]


class TicketResponse(BaseModel):
    id: uuid.UUID
    raw_text: str | None = None
    status: str
    intent: str | None = None
    category: str | None = None
    classifier_confidence: float | None = None
    decision: str | None = None
    final_answer: str | None = None
    cited_chunk_ids: list[str] | list[uuid.UUID] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class EntailmentStepTrace(BaseModel):
    """The result of the E1 entailment check for a single cited chunk."""

    chunk_id: uuid.UUID
    chunk_content_preview: str  # first 200 chars of the chunk, for the UI
    supported: bool
    reason: str


class TicketTrace(BaseModel):
    """E4 — Full per-ticket reasoning trace.

    This is the single schema that Epic F (orchestration) persists to the DB,
    GET /tickets/{id}/trace returns, and the frontend trace-viewer renders.

    Design decisions:
    - Every agent step is a typed, named field — no opaque JSON blobs.
    - threshold_used is stored explicitly so humans reviewing the trace know
      which E3 threshold was applied at decision time (useful for audits and
      threshold tuning).
    - entailment_steps is a list (one entry per cited chunk checked) so the
      UI can show which specific citation passed or failed.
    - cache_hit short-circuits the pipeline (Epic F2 semantic cache); when True,
      classifier/retriever/drafter/critic fields will be populated from cache.
    """

    ticket_id: uuid.UUID
    ticket_text: str

    # --- Classifier step ---
    intent: str
    category: str
    classifier_confidence: float

    # --- Retriever step ---
    retrieved_chunk_ids: list[uuid.UUID]        # ordered by similarity desc
    retrieved_chunk_count: int

    # --- Semantic cache (Epic F2) ---
    cache_hit: bool = False
    cached_answer: str | None = None

    # --- Drafter step ---
    draft_answer: str
    draft_cited_chunk_ids: list[uuid.UUID]
    draft_confidence: float

    # --- Critic step ---
    threshold_used: float                       # which E3 threshold was applied
    entailment_steps: list[EntailmentStepTrace] # one per cited chunk checked (E1)
    citation_supported: bool
    critic_reason: str

    # --- Final decision ---
    decision: str                               # "auto_resolve" | "escalate"
    final_answer: str | None = None             # None if escalated

