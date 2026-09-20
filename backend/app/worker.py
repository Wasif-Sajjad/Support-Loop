"""ARQ async background worker for ticket resolution pipeline.

Executes LangGraph pipeline asynchronously off the HTTP request path.
"""
import logging
import uuid
from arq import create_pool
from arq.connections import RedisSettings

from app.config import settings
from app.db import AsyncSessionLocal
from app.models import Ticket
from app.llm.base import get_provider
from app.agents.graph import build_graph
from app.cache import set_cached_answer
from sqlalchemy import select

logger = logging.getLogger(__name__)


def get_redis_settings() -> RedisSettings:
    """Parse redis_url from application settings into ARQ RedisSettings."""
    return RedisSettings.from_dsn(settings.redis_url)


async def get_arq_pool():
    """Create an ARQ redis pool connection for enqueuing jobs."""
    return await create_pool(get_redis_settings())


async def process_ticket_job(ctx: dict, ticket_id_str: str) -> dict:
    """ARQ job to execute the full triage pipeline on an enqueued ticket.

    Args:
        ctx: ARQ worker context dict.
        ticket_id_str: UUID string of the Ticket row.

    Returns:
        Summary dict of the executed pipeline output.
    """
    logger.info(f"Worker picked up ticket job: {ticket_id_str}")
    ticket_uuid = uuid.UUID(ticket_id_str)

    async with AsyncSessionLocal() as db:
        stmt = select(Ticket).where(Ticket.id == ticket_uuid)
        ticket = (await db.execute(stmt)).scalar_one_or_none()
        if not ticket:
            logger.error(f"Ticket {ticket_id_str} not found in database.")
            return {"error": "Ticket not found", "ticket_id": ticket_id_str}

        try:
            # Propagate Langfuse attributes
            from langfuse import propagate_attributes, get_client
            langfuse_client = get_client()

            with propagate_attributes(session_id=str(ticket.id), tags=["async_worker", ticket.channel]):
                llm = get_provider(settings.llm_provider)
                graph = build_graph(db, llm)
                result = await graph.ainvoke({
                    "ticket_id": ticket.id,
                    "ticket_text": ticket.raw_text,
                })

            # Update ticket record with pipeline outputs
            decision = result.get("decision", "escalate")
            ticket.intent = result.get("intent")
            ticket.category = result.get("category")
            ticket.classifier_confidence = result.get("classifier_confidence")
            ticket.final_answer = result.get("answer") if decision == "auto_resolve" else None
            ticket.cited_chunk_ids = [str(cid) for cid in result.get("cited_chunk_ids", [])]
            ticket.decision = decision
            ticket.status = "resolved" if decision == "auto_resolve" else "escalated"

            # Cache successful auto-resolve answers
            if decision == "auto_resolve" and result.get("answer"):
                trace = result.get("trace")
                cache_payload = trace.model_dump(mode="json") if trace else {
                    "final_answer": result.get("answer"),
                    "decision": decision,
                }
                await set_cached_answer(ticket.raw_text, cache_payload)

            await db.commit()
            await db.refresh(ticket)
            logger.info(f"Ticket {ticket_id_str} completed with status: {ticket.status}")

            return {
                "ticket_id": ticket_id_str,
                "status": ticket.status,
                "decision": ticket.decision,
                "intent": ticket.intent,
            }

        except Exception as exc:
            logger.exception(f"Error processing ticket {ticket_id_str}: {exc}")
            ticket.status = "failed"
            await db.commit()
            raise exc


class WorkerSettings:
    """Configuration class for arq CLI: arq app.worker.WorkerSettings"""
    functions = [process_ticket_job]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 120
