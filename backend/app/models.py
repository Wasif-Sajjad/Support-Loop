import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Float, Text, TIMESTAMP, ForeignKey, Integer, Boolean, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String, default="api")
    status: Mapped[str] = mapped_column(String, default="received")
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    classifier_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    decision: Mapped[str | None] = mapped_column(String, nullable=True)  # auto_resolved | escalated
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_chunk_ids: Mapped[list[str] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class KBChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    category_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class AgentTrace(Base):
    __tablename__ = "agent_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tickets.id"))
    agent_name: Mapped[str] = mapped_column(String)  # classifier|retriever|drafter|critic
    input: Mapped[dict] = mapped_column(JSON, nullable=True)
    output: Mapped[dict] = mapped_column(JSON, nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)


class EvalCase(Base):
    __tablename__ = "eval_set"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_text: Mapped[str] = mapped_column(Text, nullable=False)
    correct_intent: Mapped[str] = mapped_column(String, nullable=False)
    correct_decision: Mapped[str] = mapped_column(String, nullable=False)  # auto_resolve | escalate
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    git_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    wrongly_auto_resolved_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=datetime.utcnow)
