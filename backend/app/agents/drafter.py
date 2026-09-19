"""Epic D — drafts a structured, cited resolution from retrieved KB chunks.
Per NFR4: must abstain (empty citations, low confidence) rather than answer
ungrounded if retrieval found nothing relevant.
"""
import json
from app.llm.base import LLMProvider
from app.schemas import RetrievedChunk, DraftResolution


async def draft_resolution(ticket_text: str, chunks: list[RetrievedChunk], llm: LLMProvider) -> DraftResolution:
    if not chunks:
        return DraftResolution(answer="", cited_chunk_ids=[], confidence=0.0)

    context = "\n\n".join(f"[{c.chunk_id}] {c.content}" for c in chunks)
    messages = [
        {"role": "system", "content": (
            "Answer the support ticket using ONLY the provided knowledge base excerpts. "
            "Return ONLY a JSON object: {answer, cited_chunk_ids (list of the bracketed IDs "
            "you actually used), confidence (0-1)}. If the excerpts don't answer the question, "
            "return an empty answer, empty cited_chunk_ids, and confidence 0."
        )},
        {"role": "user", "content": f"Ticket: {ticket_text}\n\nKnowledge base excerpts:\n{context}"},
    ]
    response = await llm.complete(messages, response_schema=DraftResolution)
    data = json.loads(response.text)
    return DraftResolution(**data)
