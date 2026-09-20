"""Tickets router — Epic F wiring.

Exposes:
  POST /tickets          — submit ticket, run full pipeline, persist result.
  GET  /tickets/{id}     — fetch ticket record.
  GET  /tickets/{id}/trace — return the full E4 TicketTrace for a ticket.
  GET  /tickets          — list tickets, filterable by decision (escalation queue).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import Ticket, AgentTrace, EntailmentTrace
from app.schemas import TicketCreate, TicketResponse, TicketTrace, EntailmentStepTrace
from app.config import settings
from app.llm.base import get_provider
from app.agents.graph import build_graph
from app.cache import set_cached_answer

router = APIRouter(prefix="/tickets", tags=["tickets"])


import logging
from app.worker import get_arq_pool

logger = logging.getLogger(__name__)

from langfuse import observe, get_client
langfuse_client = get_client()

@router.post("", response_model=TicketResponse)
@observe(name="ticket_resolution_submit")
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Submit a raw ticket, create ticket row with status 'received', and enqueue ARQ worker job."""
    # 1. Persist ticket at "received" status immediately.
    ticket = Ticket(raw_text=payload.raw_text, channel=payload.channel, status="received")
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # Set root trace input
    langfuse_client.set_current_trace_io(
        input=payload.raw_text,
    )

    # 2. Enqueue background task in ARQ queue
    try:
        pool = await get_arq_pool()
        await pool.enqueue_job("process_ticket_job", str(ticket.id))
    except Exception as exc:
        logger.error(f"Failed to enqueue ticket {ticket.id} to ARQ worker: {exc}")

    return ticket


@router.get("/{ticket_id}/trace", response_model=TicketTrace)
async def get_ticket_trace(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TicketTrace:
    """Return the full E4 reasoning trace for a ticket.

    Reconstructs the trace from AgentTrace rows persisted by the pipeline (F3).
    This is what the frontend trace-viewer renders.

    Args:
        ticket_id: UUID of the ticket.
        db: Injected async DB session.

    Returns:
        A TicketTrace with every agent step's inputs, outputs, and decisions.

    Raises:
        404 if the ticket does not exist or has no trace rows yet.
    """
    # Fetch the ticket.
    ticket_result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = ticket_result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Fetch the agent trace rows for this ticket.
    trace_result = await db.execute(
        select(AgentTrace)
        .where(AgentTrace.ticket_id == ticket_id)
        .order_by(AgentTrace.created_at)
    )
    trace_rows = trace_result.scalars().all()

    if not trace_rows:
        raise HTTPException(
            status_code=404,
            detail="No trace available for this ticket yet. The pipeline may still be running.",
        )

    # Reconstruct TicketTrace from persisted rows + ticket record.
    # The trace was assembled by assemble_trace() during the pipeline run.
    # We rebuild it here from the DB rather than storing the full JSON blob,
    # keeping the DB schema normalised.
    classifier_row = next((r for r in trace_rows if r.agent_name == "classifier"), None)
    retriever_row = next((r for r in trace_rows if r.agent_name == "retriever"), None)
    drafter_row = next((r for r in trace_rows if r.agent_name == "drafter"), None)
    critic_row = next((r for r in trace_rows if r.agent_name == "critic"), None)
    cache_row = next((r for r in trace_rows if r.agent_name == "cache-check"), None)

    is_cache_hit = cache_row is not None and cache_row.output.get("cache_hit") is True

    if not is_cache_hit and not all([classifier_row, retriever_row, drafter_row, critic_row]):
        raise HTTPException(
            status_code=422,
            detail="Trace is incomplete — some agent steps have no recorded output.",
        )

    from app.agents.critic import STRICTER_THRESHOLD_INTENTS

    threshold = STRICTER_THRESHOLD_INTENTS.get(
        ticket.intent or "", settings.confidence_threshold
    )

    # Fetch real entailment trace rows persisted by the E1 fix.
    ent_result = await db.execute(
        select(EntailmentTrace)
        .where(EntailmentTrace.ticket_id == ticket_id)
        .order_by(EntailmentTrace.created_at)
    )
    ent_rows = ent_result.scalars().all()

    entailment_steps = [
        EntailmentStepTrace(
            chunk_id=row.chunk_id,
            chunk_content_preview=row.chunk_content_preview,
            supported=row.supported,
            reason=row.reason,
        )
        for row in ent_rows
    ]

    return TicketTrace(
        ticket_id=ticket.id,
        ticket_text=ticket.raw_text,
        # Classifier
        intent=classifier_row.output.get("intent", ticket.intent or "") if classifier_row else ticket.intent or "",
        category=classifier_row.output.get("category", ticket.category or "") if classifier_row else ticket.category or "",
        classifier_confidence=classifier_row.output.get("confidence", 0.0) if classifier_row else 0.0,
        # Retriever
        retrieved_chunk_ids=[],
        retrieved_chunk_count=retriever_row.output.get("chunk_count", 0) if retriever_row else 0,
        # Cache
        cache_hit=is_cache_hit,
        cached_answer=cache_row.output.get("cached_answer") if is_cache_hit else None,
        # Drafter
        draft_answer=drafter_row.output.get("answer", "") if drafter_row else (cache_row.output.get("cached_answer", "") if is_cache_hit else ""),
        draft_cited_chunk_ids=ticket.cited_chunk_ids or [],
        draft_confidence=drafter_row.output.get("confidence", 0.0) if drafter_row else (1.0 if is_cache_hit else 0.0),
        # Critic — now fully populated from DB
        threshold_used=threshold,
        entailment_steps=entailment_steps,
        citation_supported=critic_row.output.get("citation_supported", False) if critic_row else (True if is_cache_hit else False),
        critic_reason=critic_row.output.get("reason", "") if critic_row else ("Served from semantic cache" if is_cache_hit else ""),
        # Final
        decision=ticket.decision or "escalate",
        final_answer=ticket.final_answer,
    )



@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Fetch a single ticket by ID.

    Args:
        ticket_id: UUID of the ticket.
        db: Injected async DB session.

    Returns:
        The ticket record.

    Raises:
        404 if not found.
    """
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    decision: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[TicketResponse]:
    """List tickets, optionally filtered by decision.

    Args:
        decision: Optional filter — 'auto_resolve' or 'escalate'. Omit for all.
        db: Injected async DB session.

    Returns:
        List of ticket records ordered by creation time descending.
    """
    stmt = select(Ticket)
    if decision:
        stmt = stmt.where(Ticket.decision == decision)
    result = await db.execute(stmt.order_by(Ticket.created_at.desc()))
    return result.scalars().all()
