from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_db
from app.models import Ticket

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/summary")
async def metrics_summary(db: AsyncSession = Depends(get_db)):
    total = (await db.execute(select(func.count(Ticket.id)))).scalar_one()
    resolved = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.decision == "auto_resolve")
    )).scalar_one()
    escalated = (await db.execute(
        select(func.count(Ticket.id)).where(Ticket.decision == "escalate")
    )).scalar_one()

    return {
        "total_tickets": total,
        "resolution_rate": (resolved / total) if total else 0,
        "escalation_rate": (escalated / total) if total else 0,
        # TODO (Epic G2): populate real cost/latency aggregates from agent_traces
        "avg_cost_usd": None,
        "avg_latency_ms": None,
    }
