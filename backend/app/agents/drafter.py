"""Epic D — drafts a structured, grounded resolution from retrieved KB chunks.

Story coverage:
  D1 — Output schema: {answer: str, cited_chunk_ids: list[UUID], confidence: float}
       enforced via Pydantic (DraftResolution). Schema lives in app/schemas.py.
  D2 — Drafting prompt forces citation of specific bracketed chunk IDs and explicitly
       forbids answering beyond what the retrieved content says.
  D3 — Empty-retrieval fast-path: if no chunks are available, return a structured
       abstain response (empty answer, empty citations, confidence=0.0) immediately
       without calling the LLM, satisfying NFR4 (no hallucination on empty retrieval).
"""
import json
import uuid

from app.llm.base import LLMProvider
from app.schemas import RetrievedChunk, DraftResolution

# Minimum similarity score below which a chunk is considered too weak to cite.
# Chunks below this threshold are dropped before the LLM sees them.
MIN_SIMILARITY_THRESHOLD = 0.30

_SYSTEM_PROMPT = """\
You are a support resolution drafter. Your ONLY job is to write an answer to the \
support ticket using the knowledge base excerpts provided below.

STRICT RULES — violating any of these rules makes the answer invalid:
1. Use ONLY information from the provided excerpts. Do NOT use any outside knowledge.
2. Every factual claim in your answer MUST be traceable to at least one excerpt.
3. In `cited_chunk_ids`, list ONLY the bracketed IDs of excerpts you actually used.
   Do not include an ID if you did not quote or paraphrase it.
4. If the excerpts do not contain enough information to answer the ticket, you MUST
   return: {"answer": "", "cited_chunk_ids": [], "confidence": 0.0}
   Do NOT guess, speculate, or fill gaps with general knowledge.
5. Return ONLY a JSON object with exactly three keys:
   - answer (string): your drafted response, or empty string if abstaining
   - cited_chunk_ids (list of strings): UUIDs from the bracketed IDs you used
   - confidence (float 0.0–1.0): your confidence that the answer fully resolves the ticket
"""


async def draft_resolution(
    ticket_text: str,
    chunks: list[RetrievedChunk],
    llm: LLMProvider,
) -> DraftResolution:
    """Draft a grounded, cited resolution for a support ticket.

    Story D3: If no chunks are provided (retriever returned empty), immediately
    returns a structured abstain response without making any LLM call.

    Story D2: The system prompt strictly forbids answering beyond the retrieved
    content and requires citing specific chunk IDs.

    Args:
        ticket_text: The raw support ticket text from the user.
        chunks: Retrieved KB chunks from the retriever agent. May be empty.
        llm: An LLMProvider instance (via app.llm.base.get_provider).

    Returns:
        A DraftResolution. If abstaining, answer is empty string, cited_chunk_ids
        is empty, and confidence is 0.0.

    Raises:
        json.JSONDecodeError: If the LLM returns malformed JSON.
        ValueError: If the LLM response fails Pydantic validation.
    """
    # D3 — Empty-retrieval fast-path: abstain immediately, no LLM call.
    if not chunks:
        return DraftResolution(answer="", cited_chunk_ids=[], confidence=0.0)

    # Filter out very low-similarity chunks that would only confuse the drafter.
    strong_chunks = [c for c in chunks if c.similarity >= MIN_SIMILARITY_THRESHOLD]
    if not strong_chunks:
        return DraftResolution(answer="", cited_chunk_ids=[], confidence=0.0)

    # Format chunks as bracketed entries so the LLM can reference them by ID.
    context_lines = [
        f"[{c.chunk_id}]\n{c.content.strip()}"
        for c in strong_chunks
    ]
    context_block = "\n\n---\n\n".join(context_lines)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Support ticket:\n{ticket_text}\n\n"
                f"Knowledge base excerpts:\n{context_block}\n\n"
                "Return your JSON response now."
            ),
        },
    ]

    response = await llm.complete(messages, response_schema=DraftResolution)

    # Strip markdown fences if the LLM wrapped the JSON (defensive parsing).
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    data = json.loads(raw)

    # Normalise cited_chunk_ids: LLM may return strings or UUIDs — cast all to uuid.UUID.
    raw_ids = data.get("cited_chunk_ids", [])
    try:
        data["cited_chunk_ids"] = [uuid.UUID(str(cid)) for cid in raw_ids]
    except (ValueError, AttributeError):
        # If IDs are malformed, treat as no citation → will trigger escalation in critic.
        data["cited_chunk_ids"] = []

    return DraftResolution(**data)

