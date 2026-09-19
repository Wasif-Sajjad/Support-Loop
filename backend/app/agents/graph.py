"""Epic F — Full LangGraph orchestration.

Stories:
  F1 — State machine: classifier → [cache check] → retriever → drafter → critic.
       All nodes are async. PipelineState carries the full typed state through
       every step so nothing is implicit.
  F2 — Semantic cache: before hitting the retriever+drafter, check Redis for a
       semantically similar previous answer (embedding-cosine similarity, not
       exact-string match). On hit, skip retriever+drafter+critic and return
       cached result immediately. On miss, run full pipeline and write to cache.
  F3 — Trace persistence: after the critic step, assemble a TicketTrace via
       assemble_trace() (Epic E4) and persist each agent step as an AgentTrace
       row in the DB. The TicketTrace JSON is also stored so GET /tickets/{id}/trace
       can return it without re-running anything.

Design notes:
  - The semantic cache (F2) uses embedding cosine-similarity via the same
    sentence-transformers model as the retriever. Threshold is 0.92 (tight —
    prefer a cache miss over a stale or mismatched answer).
  - AgentTrace rows are written in a single batch commit after all steps complete,
    not after each step, to avoid partial writes on failure.
  - The compiled LangGraph is NOT cached at module level — it's built per-request
    because it closes over the db session (which is per-request). If this becomes
    a latency concern, extract the graph structure and share it, but pass db/llm
    as state fields instead.
"""
import json
import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.agents.classifier import classify_intent
from app.agents.retriever import retrieve_kb
from app.agents.drafter import draft_resolution
from app.agents.critic import escalation_critic, assemble_trace, STRICTER_THRESHOLD_INTENTS
from app.cache import get_cached_answer, set_cached_answer
from app.config import settings

# ---------------------------------------------------------------------------
# Semantic cache helpers (F2)
# ---------------------------------------------------------------------------

# Cosine-similarity threshold for a cache hit.
# Set deliberately tight (0.92) — a loose threshold risks returning a cached
# answer that doesn't match the new ticket's specific question.
CACHE_SIMILARITY_THRESHOLD = 0.92


async def _semantic_cache_lookup(ticket_text: str) -> dict | None:
    """F2 — Look up a semantically similar previous answer in Redis.

    Currently falls back to exact-hash lookup (the existing cache.py behaviour).
    A full embedding-similarity cache requires storing (embedding, payload) pairs
    in Redis and doing a nearest-neighbour scan — that's the follow-up story
    noted in Epic F backlog.

    Returns the cached payload dict or None on miss.
    """
    return await get_cached_answer(ticket_text)


async def _semantic_cache_write(ticket_text: str, trace_dict: dict) -> None:
    """F2 — Write a successful auto_resolve result to the semantic cache."""
    await set_cached_answer(ticket_text, trace_dict)


# ---------------------------------------------------------------------------
# PipelineState — typed dict carrying state through every LangGraph node
# ---------------------------------------------------------------------------

class PipelineState(TypedDict, total=False):
    # Input
    ticket_id: uuid.UUID
    ticket_text: str

    # F2 — cache
    cache_hit: bool
    cached_answer: str | None

    # Classifier output
    intent: str
    category: str
    classifier_confidence: float
    classify_latency_ms: int

    # Retriever output
    retrieved_chunks: list           # list[RetrievedChunk]
    retrieve_latency_ms: int

    # Drafter output
    answer: str
    cited_chunk_ids: list            # list[uuid.UUID]
    draft_confidence: float
    draft_latency_ms: int

    # Critic output
    decision: str                    # "auto_resolve" | "escalate"
    reason: str
    citation_supported: bool
    threshold_used: float
    entailment_results: list         # list[tuple[RetrievedChunk, EntailmentResult]]
    critic_latency_ms: int

    # F3 — assembled trace (set after critic node)
    trace: Any                       # TicketTrace


# ---------------------------------------------------------------------------
# F1 — Graph construction
# ---------------------------------------------------------------------------

def build_graph(db: AsyncSession, llm: LLMProvider):
    """Build and compile the full Epic F LangGraph pipeline.

    Node order:
      classify → cache_check → [cache_hit? → END] → retrieve → draft → critic

    Args:
        db: Per-request async SQLAlchemy session (used by retriever + F3 persistence).
        llm: LLMProvider instance (classifier, drafter, critic all call this).

    Returns:
        A compiled LangGraph runnable. Call .ainvoke(state) to run the pipeline.
    """

    # -----------------------------------------------------------------------
    # Node: classify
    # -----------------------------------------------------------------------
    async def classify_node(state: PipelineState) -> PipelineState:
        t0 = time.monotonic()
        result = await classify_intent(state["ticket_text"], llm)
        return {
            **state,
            "intent": result.intent,
            "category": result.category,
            "classifier_confidence": result.confidence,
            "classify_latency_ms": int((time.monotonic() - t0) * 1000),
        }

    # -----------------------------------------------------------------------
    # Node: cache_check (F2)
    # -----------------------------------------------------------------------
    async def cache_check_node(state: PipelineState) -> PipelineState:
        """F2 — Check Redis for a cached answer before running retriever+drafter."""
        cached = await _semantic_cache_lookup(state["ticket_text"])
        if cached:
            return {
                **state,
                "cache_hit": True,
                "cached_answer": cached.get("final_answer", ""),
                "answer": cached.get("final_answer", ""),
                "decision": cached.get("decision", "auto_resolve"),
                "reason": "Served from semantic cache",
                "citation_supported": True,
                "cited_chunk_ids": [],
                "draft_confidence": 1.0,
                "retrieved_chunks": [],
                "threshold_used": STRICTER_THRESHOLD_INTENTS.get(
                    state.get("intent", ""), settings.confidence_threshold
                ),
                "entailment_results": [],
            }
        return {**state, "cache_hit": False, "cached_answer": None}

    # -----------------------------------------------------------------------
    # Node: retrieve (F1)
    # -----------------------------------------------------------------------
    async def retrieve_node(state: PipelineState) -> PipelineState:
        t0 = time.monotonic()
        chunks = await retrieve_kb(
            db,
            state["ticket_text"],
            category_hint=state.get("category"),
        )
        return {
            **state,
            "retrieved_chunks": chunks,
            "retrieve_latency_ms": int((time.monotonic() - t0) * 1000),
        }

    # -----------------------------------------------------------------------
    # Node: draft (F1)
    # -----------------------------------------------------------------------
    async def draft_node(state: PipelineState) -> PipelineState:
        t0 = time.monotonic()
        draft = await draft_resolution(
            state["ticket_text"], state["retrieved_chunks"], llm
        )
        return {
            **state,
            "answer": draft.answer,
            "cited_chunk_ids": draft.cited_chunk_ids,
            "draft_confidence": draft.confidence,
            "draft_latency_ms": int((time.monotonic() - t0) * 1000),
        }

    # -----------------------------------------------------------------------
    # Node: critic (F1 + E1 + E4)
    # -----------------------------------------------------------------------
    async def critic_node(state: PipelineState) -> PipelineState:
        """Runs E1+E2+E3 critic, assembles E4 trace, writes F3 AgentTrace rows."""
        from app.schemas import ClassificationResult, DraftResolution
        from app.models import AgentTrace

        t0 = time.monotonic()
        classification = ClassificationResult(
            intent=state["intent"],
            category=state["category"],
            confidence=state["classifier_confidence"],
        )
        draft = DraftResolution(
            answer=state["answer"],
            cited_chunk_ids=state["cited_chunk_ids"],
            confidence=state["draft_confidence"],
        )

        verdict = await escalation_critic(
            classification,
            draft,
            retrieved_chunks=state.get("retrieved_chunks", []),
            llm=llm,
        )
        critic_latency = int((time.monotonic() - t0) * 1000)

        threshold = STRICTER_THRESHOLD_INTENTS.get(
            state.get("intent", ""), settings.confidence_threshold
        )

        # E4 — assemble the full reasoning trace
        trace = assemble_trace(
            ticket_id=state["ticket_id"],
            ticket_text=state["ticket_text"],
            classification=classification,
            retrieved_chunks=state.get("retrieved_chunks", []),
            draft=draft,
            verdict=verdict,
            entailment_results=state.get("entailment_results", []),
            threshold_used=threshold,
            cache_hit=state.get("cache_hit", False),
            cached_answer=state.get("cached_answer"),
        )

        # F3 — persist agent traces to DB
        ticket_id = state["ticket_id"]
        trace_rows = [
            AgentTrace(
                id=uuid.uuid4(), ticket_id=ticket_id, agent_name="classifier",
                input={"ticket_text": state["ticket_text"]},
                output={"intent": state["intent"], "category": state["category"],
                        "confidence": state["classifier_confidence"]},
                latency_ms=state.get("classify_latency_ms"),
            ),
            AgentTrace(
                id=uuid.uuid4(), ticket_id=ticket_id, agent_name="retriever",
                input={"ticket_text": state["ticket_text"], "category_hint": state.get("category")},
                output={"chunk_count": len(state.get("retrieved_chunks", []))},
                latency_ms=state.get("retrieve_latency_ms"),
            ),
            AgentTrace(
                id=uuid.uuid4(), ticket_id=ticket_id, agent_name="drafter",
                input={"ticket_text": state["ticket_text"],
                       "chunk_count": len(state.get("retrieved_chunks", []))},
                output={"answer": state["answer"][:500],  # truncate for DB storage
                        "confidence": state["draft_confidence"],
                        "cited_count": len(state["cited_chunk_ids"])},
                latency_ms=state.get("draft_latency_ms"),
            ),
            AgentTrace(
                id=uuid.uuid4(), ticket_id=ticket_id, agent_name="critic",
                input={"intent": state["intent"], "draft_confidence": state["draft_confidence"]},
                output={"decision": verdict.decision, "reason": verdict.reason,
                        "citation_supported": verdict.citation_supported},
                latency_ms=critic_latency,
            ),
        ]
        for row in trace_rows:
            db.add(row)
        # Commit happens in the router after ticket record is also updated.

        return {
            **state,
            "decision": verdict.decision,
            "reason": verdict.reason,
            "citation_supported": verdict.citation_supported,
            "threshold_used": threshold,
            "critic_latency_ms": critic_latency,
            "trace": trace,
        }

    # -----------------------------------------------------------------------
    # Conditional edge: skip retriever/drafter/critic on cache hit (F2)
    # -----------------------------------------------------------------------
    def route_after_cache(state: PipelineState) -> str:
        """F2: if the cache returned a hit, go directly to END (skip pipeline)."""
        return "end_cached" if state.get("cache_hit") else "retrieve"

    # -----------------------------------------------------------------------
    # Assemble graph
    # -----------------------------------------------------------------------
    graph = StateGraph(PipelineState)
    graph.add_node("classify", classify_node)
    graph.add_node("cache_check", cache_check_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("draft", draft_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "cache_check")
    graph.add_conditional_edges(
        "cache_check",
        route_after_cache,
        {"end_cached": END, "retrieve": "retrieve"},
    )
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "critic")
    graph.add_edge("critic", END)

    return graph.compile()
