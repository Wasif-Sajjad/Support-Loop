import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import Ticket
from app.schemas import TicketCreate, TicketResponse
from app.config import settings
from app.llm.base import get_provider
from app.agents.graph import build_graph

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post("", response_model=TicketResponse)
async def create_ticket(payload: TicketCreate, db: AsyncSession = Depends(get_db)):
    ticket = Ticket(raw_text=payload.raw_text, status="received")
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # Run the pipeline synchronously for the starter version.
    # TODO (Epic F): move this to a background task/queue for real async processing.
    llm = get_provider(settings.llm_provider)
    graph = build_graph(db, llm)
    result = await graph.ainvoke({"ticket_text": ticket.raw_text})

    ticket.intent = result.get("intent")
    ticket.category = result.get("category")
    ticket.classifier_confidence = result.get("classifier_confidence")
    ticket.final_answer = result.get("answer")
    ticket.decision = result.get("decision")
    ticket.status = "resolved" if result.get("decision") == "auto_resolve" else "escalated"
    await db.commit()
    await db.refresh(ticket)

    return ticket


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("", response_model=list[TicketResponse])
async def list_tickets(decision: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Ticket)
    if decision:
        stmt = stmt.where(Ticket.decision == decision)
    result = await db.execute(stmt.order_by(Ticket.created_at.desc()))
    return result.scalars().all()
