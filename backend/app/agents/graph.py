"""Epic F — wires classifier -> retriever -> drafter -> critic into a LangGraph state
machine. This is a minimal starting skeleton; add the semantic-cache short-circuit
(F2) and full trace persistence (F3) as their own stories.
"""
from typing import TypedDict
from langgraph.graph import StateGraph, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.base import LLMProvider
from app.agents.classifier import classify_intent
from app.agents.retriever import retrieve_kb
from app.agents.drafter import draft_resolution
from app.agents.critic import escalation_critic


class PipelineState(TypedDict, total=False):
    ticket_text: str
    intent: str
    category: str
    classifier_confidence: float
    retrieved_chunks: list
    answer: str
    cited_chunk_ids: list
    draft_confidence: float
    decision: str
    reason: str


def build_graph(db: AsyncSession, llm: LLMProvider):
    async def classify_node(state: PipelineState) -> PipelineState:
        result = await classify_intent(state["ticket_text"], llm)
        return {**state, "intent": result.intent, "category": result.category,
                "classifier_confidence": result.confidence}

    async def retrieve_node(state: PipelineState) -> PipelineState:
        chunks = await retrieve_kb(db, state["ticket_text"], category_hint=state.get("category"))
        return {**state, "retrieved_chunks": chunks}

    async def draft_node(state: PipelineState) -> PipelineState:
        draft = await draft_resolution(state["ticket_text"], state["retrieved_chunks"], llm)
        return {**state, "answer": draft.answer, "cited_chunk_ids": draft.cited_chunk_ids,
                "draft_confidence": draft.confidence}

    def critic_node(state: PipelineState) -> PipelineState:
        from app.schemas import ClassificationResult, DraftResolution
        classification = ClassificationResult(
            intent=state["intent"], category=state["category"], confidence=state["classifier_confidence"]
        )
        draft = DraftResolution(
            answer=state["answer"], cited_chunk_ids=state["cited_chunk_ids"], confidence=state["draft_confidence"]
        )
        verdict = escalation_critic(classification, draft)
        return {**state, "decision": verdict.decision, "reason": verdict.reason}

    graph = StateGraph(PipelineState)
    graph.add_node("classify", classify_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("draft", draft_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "critic")
    graph.add_edge("critic", END)

    return graph.compile()
