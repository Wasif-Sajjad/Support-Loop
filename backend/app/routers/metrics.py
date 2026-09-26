from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.db import get_db
from app.models import Ticket, AgentTrace
from app.llm.pricing import COST_DISCLAIMER

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

    # Per-ticket cost and latency aggregates from agent_traces
    # We sum cost and latency per ticket, then average across all tickets that have traces.
    ticket_trace_stats_subq = (
        select(
            AgentTrace.ticket_id,
            func.sum(AgentTrace.cost_usd).label("ticket_cost"),
            func.sum(AgentTrace.latency_ms).label("ticket_latency"),
        )
        .group_by(AgentTrace.ticket_id)
        .subquery()
    )

    agg_result = await db.execute(
        select(
            func.avg(ticket_trace_stats_subq.c.ticket_cost),
            func.avg(ticket_trace_stats_subq.c.ticket_latency),
        )
    )
    avg_cost, avg_latency = agg_result.one()

    # Provider breakdown: group LLM traces by provider name in output JSON
    traces_result = await db.execute(
        select(
            AgentTrace.agent_name,
            AgentTrace.output,
            AgentTrace.tokens_in,
            AgentTrace.tokens_out,
            AgentTrace.cost_usd,
            AgentTrace.latency_ms,
        ).where(
            AgentTrace.agent_name.in_(["classifier", "drafter", "critic"])
        )
    )
    llm_traces = traces_result.all()

    provider_breakdown: dict[str, dict] = {
        "groq": {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "total_latency_ms": 0},
        "gemini": {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "total_latency_ms": 0},
    }

    for row in llm_traces:
        output_data = row.output or {}
        p_name = output_data.get("provider") or "groq"
        p_key = "gemini" if "gemini" in p_name.lower() else "groq"
        if p_key not in provider_breakdown:
            provider_breakdown[p_key] = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "total_latency_ms": 0}

        entry = provider_breakdown[p_key]
        entry["calls"] += 1
        entry["tokens_in"] += row.tokens_in or 0
        entry["tokens_out"] += row.tokens_out or 0
        entry["cost_usd"] = round(entry["cost_usd"] + (row.cost_usd or 0.0), 8)
        entry["total_latency_ms"] += row.latency_ms or 0

    from app.llm.groq_provider import DEFAULT_MODEL as GROQ_MODEL
    from app.llm.gemini_provider import DEFAULT_MODEL as GEMINI_MODEL

    active_models = {
        "groq": GROQ_MODEL,
        "gemini": GEMINI_MODEL,
    }

    # Format provider stats with average latency and dynamic active model name
    formatted_providers = {}
    # Ensure both primary providers are present in the response
    for key in ("groq", "gemini"):
        stats = provider_breakdown.get(key, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "total_latency_ms": 0})
        calls = stats["calls"]
        formatted_providers[key] = {
            "calls": calls,
            "tokens_in": stats["tokens_in"],
            "tokens_out": stats["tokens_out"],
            "cost_usd": round(stats["cost_usd"], 6),
            "avg_latency_ms": int(stats["total_latency_ms"] / calls) if calls > 0 else 0,
            "pricing_label": COST_DISCLAIMER,
            "model_name": active_models.get(key, key),
        }

    # Include any additional providers from traces (e.g. cerebras, ollama)
    for p_key, stats in provider_breakdown.items():
        if p_key not in formatted_providers:
            calls = stats["calls"]
            formatted_providers[p_key] = {
                "calls": calls,
                "tokens_in": stats["tokens_in"],
                "tokens_out": stats["tokens_out"],
                "cost_usd": round(stats["cost_usd"], 6),
                "avg_latency_ms": int(stats["total_latency_ms"] / calls) if calls > 0 else 0,
                "pricing_label": COST_DISCLAIMER,
                "model_name": active_models.get(p_key, p_key),
            }

    return {
        "total_tickets": total,
        "resolution_rate": (resolved / total) if total else 0,
        "escalation_rate": (escalated / total) if total else 0,
        "avg_cost_usd": round(float(avg_cost), 6) if avg_cost is not None else 0.0,
        "avg_latency_ms": int(avg_latency) if avg_latency is not None else 0,
        "pricing_disclaimer": COST_DISCLAIMER,
        "provider_breakdown": formatted_providers,
    }
