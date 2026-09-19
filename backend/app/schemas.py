"""Pydantic schemas — the structured-output contracts every agent must honor.
Per AGENTS.md: no agent may return free text as a final output; everything goes
through one of these models first.
"""
import uuid
from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    raw_text: str = Field(..., min_length=1)
    channel: str = "api"


class ClassificationResult(BaseModel):
    intent: str
    category: str
    confidence: float = Field(..., ge=0, le=1)


class RetrievedChunk(BaseModel):
    chunk_id: uuid.UUID
    content: str
    similarity: float


class DraftResolution(BaseModel):
    answer: str
    cited_chunk_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence: float = Field(..., ge=0, le=1)


class CriticVerdict(BaseModel):
    decision: str  # "auto_resolve" | "escalate"
    reason: str
    citation_supported: bool


class TicketResponse(BaseModel):
    id: uuid.UUID
    status: str
    intent: str | None = None
    category: str | None = None
    decision: str | None = None
    final_answer: str | None = None

    class Config:
        from_attributes = True
