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
from app.models import Ticket, AgentTrace
from app.schemas import TicketCreate, TicketResponse, TicketTrace
from app.config import settings
from app.llm.base import get_provider
from app.agents.graph import build_graph
from app.cache import set_cached_answer

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse)
async def create_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
) -> TicketResponse:
    """Submit a raw ticket, run the full agent pipeline, persist the result.

    The pipeline runs synchronously in the request (acceptable for async
    support workflows — p50 < 5s per NFR5). A background task queue can be
    added later without changing this interface.

    Args:
        payload: TicketCreate with raw_text and optional channel.
        db: Injected async DB session.

    Returns:
        The persisted ticket record with intent, decision, and final_answer.
    """
    # 1. Persist ticket at "received" status first so we have a UUID for traces.
    ticket = Ticket(raw_text=payload.raw_text, channel=payload.channel, status="received")
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # 2. Run the full Epic F pipeline.
    llm = get_provider(settings.llm_provider)
    graph = build_graph(db, llm)
    result = await graph.ainvoke({
        "ticket_id": ticket.id,
        "ticket_text": ticket.raw_text,
    })

    # 3. Update ticket record with pipeline outputs.
    ticket.intent = result.get("intent")
    ticket.category = result.get("category")
    ticket.classifier_confidence = result.get("classifier_confidence")
    ticket.final_answer = result.get("answer") if result.get("decision") == "auto_resolve" else None
    ticket.cited_chunk_ids = [str(cid) for cid in result.get("cited_chunk_ids", [])]
    ticket.decision = result.get("decision")
    ticket.status = "resolved" if result.get("decision") == "auto_resolve" else "escalated"

    await db.commit()
    await db.refresh(ticket)

    # 4. F2 — write successful auto-resolve answers to the semantic cache.
    if result.get("decision") == "auto_resolve" and result.get("answer"):
        trace = result.get("trace")
        cache_payload = trace.model_dump(mode="json") if trace else {
            "final_answer": result.get("answer"),
            "decision": result.get("decision"),
        }
        await set_cached_answer(ticket.raw_text, cache_payload)

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

    if not all([classifier_row, retriever_row, drafter_row, critic_row]):
        raise HTTPException(
            status_code=422,
            detail="Trace is incomplete — some agent steps have no recorded output.",
        )

    from app.schemas import EntailmentStepTrace
    from app.agents.critic import STRICTER_THRESHOLD_INTENTS

    threshold = STRICTER_THRESHOLD_INTENTS.get(
        ticket.intent or "", settings.confidence_threshold
    )

    return TicketTrace(
        ticket_id=ticket.id,
        ticket_text=ticket.raw_text,
        # Classifier
        intent=classifier_row.output.get("intent", ticket.intent or ""),
        category=classifier_row.output.get("category", ticket.category or ""),
        classifier_confidence=classifier_row.output.get("confidence", 0.0),
        # Retriever
        retrieved_chunk_ids=[],     # chunk UUIDs not stored individually in AgentTrace
        retrieved_chunk_count=retriever_row.output.get("chunk_count", 0),
        # Cache
        cache_hit=False,            # cache hits are never persisted as trace rows
        cached_answer=None,
        # Drafter
        draft_answer=drafter_row.output.get("answer", ""),
        draft_cited_chunk_ids=[uuid.UUID(cid) for cid in (ticket.cited_chunk_ids or [])],
        draft_confidence=drafter_row.output.get("confidence", 0.0),
        # Critic
        threshold_used=threshold,
        entailment_steps=[],        # entailment details not stored per-step in DB yet
        citation_supported=critic_row.output.get("citation_supported", False),
        critic_reason=critic_row.output.get("reason", ""),
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
