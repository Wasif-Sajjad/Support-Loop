"""Epic E — the escalation critic.

Applies checks in strict priority order:
  1. (E2) Hard policy denylist — always escalate, no LLM call.
  2. (E3) Confidence floor + citation presence — escalate if below threshold.
  3. (E1) Citation entailment — real LLM call: does the cited chunk actually
         support the drafted answer? Escalate if it doesn't.
  4. (E4) assemble_trace() collects all agent outputs into a TicketTrace that
         Epic F persists and the frontend renders.

Story coverage:
  E1 — entailment_check() replaces the old `citation_supported = True` stub.
       Makes a small, focused LLM call that returns structured EntailmentResult.
  E2 — POLICY_DENYLIST_INTENTS = {delete_account, complaint}. Unit-tested in
       backend/tests/test_critic.py::test_e2_denylist_*.
  E3 — Thresholds are PROVISIONAL DEFAULTS ONLY.
       ⚠ DO NOT tune against the current 13-row eval set — it is too small and
       6 of 9 account intents still lack KB content. Any tuning now would fit
       noise, not signal. Revisit once:
         (a) docs/eval_set.csv reaches 50+ rows (see docs/eval_set_README.md), AND
         (b) all 10 intent KB sources are complete (see Epic B backlog).
       Backlog item: "Tune E3 thresholds after Epic B KB completion + eval expansion".
  E4 — assemble_trace() builds the structured reasoning trace that Epic F persists
       and the frontend renders.
"""
import json

from app.llm.base import LLMProvider
from app.schemas import (
    ClassificationResult,
    CriticVerdict,
    CriticVerdictWithTrace,
    DraftResolution,
    EntailmentResult,
    EntailmentStepTrace,
    RetrievedChunk,
    TicketTrace,
)
from app.config import settings
import uuid as _uuid

# ---------------------------------------------------------------------------
# E2 — Hard policy denylist
# ---------------------------------------------------------------------------
# These intents ALWAYS escalate, regardless of confidence or citation quality.
# - delete_account: irreversible/destructive; requires human sign-off.
# - complaint: reputational/sensitive; requires human sign-off.
# ⚠ Do not expand this list without a corresponding update to docs/eval_set.csv.
POLICY_DENYLIST_INTENTS: frozenset[str] = frozenset({"delete_account", "complaint"})

# ---------------------------------------------------------------------------
# E3 — Confidence thresholds (PROVISIONAL — see module docstring before tuning)
# ---------------------------------------------------------------------------
# General floor: 0.7 (from settings.confidence_threshold / .env CONFIDENCE_THRESHOLD).
# Stricter per-intent overrides for intents that carry production risk.
STRICTER_THRESHOLD_INTENTS: dict[str, float] = {
    "infrastructure_issue": 0.9,
    # Backlog: add more overrides here after E3 tuning story is executed.
}

# ---------------------------------------------------------------------------
# E1 — Entailment check prompt
# ---------------------------------------------------------------------------
_ENTAILMENT_SYSTEM_PROMPT = """\
You are a citation auditor. You will be shown:
  1. A drafted support answer.
  2. A knowledge base passage that was cited in that answer.

Your job: decide whether the passage provides factual support for the drafted answer.

Return ONLY a JSON object with exactly two keys:
  - supported (boolean): true if the passage provides source material for AT LEAST ONE 
    claim in the answer. It does not need to support the entire answer (other passages 
    might cover the rest). False ONLY if it is completely off-topic, unused, or contradicted.
  - reason (string): one or two sentences explaining your decision.

Do not consider whether the answer is generally correct — only whether THIS passage
was actually used as factual grounding for some part of the answer.
Return ONLY valid JSON, no markdown fences.
"""


async def entailment_check(
    answer: str,
    cited_chunk: RetrievedChunk,
    llm: LLMProvider,
) -> EntailmentResult:
    """E1 — Ask the LLM whether a cited KB chunk actually supports the drafted answer.

    This replaces the old `citation_supported = True` stub. The LLM makes a
    focused yes/no judgment with a brief reason, returned as structured output.

    Args:
        answer: The drafted answer text from the drafter agent.
        cited_chunk: One of the chunks cited in the draft. We check one chunk per call;
            the caller may run this for multiple chunks and aggregate.
        llm: An LLMProvider instance (via app.llm.base.get_provider).

    Returns:
        An EntailmentResult with supported (bool) and reason (str).

    Raises:
        json.JSONDecodeError: If the LLM returns malformed JSON.
        ValueError: If the response fails EntailmentResult validation.
    """
    messages = [
        {"role": "system", "content": _ENTAILMENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Drafted answer:\n{answer}\n\n"
                f"Cited passage:\n{cited_chunk.content.strip()}\n\n"
                "Does this passage support the answer? Return JSON now."
            ),
        },
    ]
    response = await llm.complete(messages, response_schema=EntailmentResult)

    # Defensive parse: strip markdown fences if present.
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    data = json.loads(raw)
    result = EntailmentResult(**data)
    result.tokens_in = response.tokens_in
    result.tokens_out = response.tokens_out
    result.cost_usd = response.cost_usd
    result.latency_ms = response.latency_ms
    result.provider_name = response.provider_name
    return result


# ---------------------------------------------------------------------------
# Main critic function
# ---------------------------------------------------------------------------

async def escalation_critic(
    classification: ClassificationResult,
    draft: DraftResolution,
    retrieved_chunks: list[RetrievedChunk],
    llm: LLMProvider,
) -> CriticVerdictWithTrace:
    """Decide whether a drafted answer should be auto-resolved or escalated.

    Applies three checks in strict priority order:

    1. (E2) Hard policy denylist: some intents always escalate. No LLM call.
    2. (E3) Confidence floor + citation presence: escalate if below threshold. No LLM call.
    3. (E1) Citation entailment: LLM call for EVERY cited chunk. Escalates if ANY
       chunk fails. This fixes the original bug where only the first chunk was checked.

    Args:
        classification: Output of the classifier agent.
        draft: Output of the drafter agent.
        retrieved_chunks: The chunks returned by the retriever (used to look up
            cited chunk content for the entailment check).
        llm: An LLMProvider instance (via app.llm.base.get_provider).

    Returns:
        A CriticVerdictWithTrace — the verdict plus every (chunk, EntailmentResult)
        pair checked, so the caller can persist EntailmentTrace rows and assemble
        the full TicketTrace.entailment_steps.
    """
    def _short_circuit(verdict: CriticVerdict) -> CriticVerdictWithTrace:
        """Return a verdict with an empty entailment list (pre-entailment escalation)."""
        return CriticVerdictWithTrace(verdict=verdict, entailment_results=[])

    # --- Check 1 (E2): Hard policy denylist ---
    if classification.intent in POLICY_DENYLIST_INTENTS:
        return _short_circuit(CriticVerdict(
            decision="escalate",
            reason=f"Policy denylist: intent '{classification.intent}' always requires human review",
            citation_supported=False,
        ))

    # --- Check 2 (E3): Confidence floor + citation presence ---
    threshold = STRICTER_THRESHOLD_INTENTS.get(
        classification.intent, settings.confidence_threshold
    )
    if not draft.cited_chunk_ids or draft.confidence < threshold:
        return _short_circuit(CriticVerdict(
            decision="escalate",
            reason=(
                f"Confidence {draft.confidence:.2f} below threshold {threshold} "
                f"or no supporting citation"
            ),
            citation_supported=bool(draft.cited_chunk_ids),
        ))

    # --- Check 3 (E1): Citation entailment — check EVERY cited chunk ---
    chunk_map: dict[str, RetrievedChunk] = {
        str(c.chunk_id): c for c in retrieved_chunks
    }

    entailment_results: list[tuple[RetrievedChunk, EntailmentResult]] = []
    hallucinated_ids: list[str] = []

    for cited_id in draft.cited_chunk_ids:
        cited_id_str = str(cited_id)
        chunk = chunk_map.get(cited_id_str)

        if chunk is None:
            # This cited ID was not in the retrieved set — hallucinated.
            hallucinated_ids.append(cited_id_str)
            continue

        result = await entailment_check(draft.answer, chunk, llm)
        entailment_results.append((chunk, result))

    # Any hallucinated IDs → immediate escalation (no entailment possible).
    if hallucinated_ids:
        return CriticVerdictWithTrace(
            verdict=CriticVerdict(
                decision="escalate",
                reason=(
                    f"{len(hallucinated_ids)} cited chunk ID(s) were not in the retrieved "
                    f"set — possible hallucination: {', '.join(hallucinated_ids[:3])}"
                ),
                citation_supported=False,
            ),
            entailment_results=entailment_results,
        )

    # If no entailment results (all IDs hallucinated OR draft had no citations after
    # the confidence check — shouldn't happen but guard anyway).
    if not entailment_results:
        return CriticVerdictWithTrace(
            verdict=CriticVerdict(
                decision="escalate",
                reason="No valid cited chunks could be entailment-checked.",
                citation_supported=False,
            ),
            entailment_results=[],
        )

    # Find the first failing chunk (if any).
    failing = [(chunk, r) for chunk, r in entailment_results if not r.supported]

    if failing:
        fail_chunk, fail_result = failing[0]
        return CriticVerdictWithTrace(
            verdict=CriticVerdict(
                decision="escalate",
                reason=(
                    f"Entailment failed for chunk {fail_chunk.chunk_id}: "
                    f"{fail_result.reason} "
                    f"({len(failing)}/{len(entailment_results)} chunks failed)"
                ),
                citation_supported=False,
            ),
            entailment_results=entailment_results,
        )

    # All chunks passed.
    passed_summary = "; ".join(r.reason[:80] for _, r in entailment_results[:2])
    return CriticVerdictWithTrace(
        verdict=CriticVerdict(
            decision="auto_resolve",
            reason=f"All {len(entailment_results)} citation(s) passed entailment. {passed_summary}",
            citation_supported=True,
        ),
        entailment_results=entailment_results,
    )


# ---------------------------------------------------------------------------
# E4 — Reasoning trace assembly
# ---------------------------------------------------------------------------

def assemble_trace(
    ticket_id: _uuid.UUID,
    ticket_text: str,
    classification: ClassificationResult,
    retrieved_chunks: list[RetrievedChunk],
    draft: DraftResolution,
    verdict: CriticVerdict,
    entailment_results: list[tuple[RetrievedChunk, EntailmentResult]],
    threshold_used: float,
    cache_hit: bool = False,
    cached_answer: str | None = None,
) -> TicketTrace:
    """E4 — Assemble a complete, structured reasoning trace for one ticket.

    Called by the Epic F orchestrator after all agent steps complete.
    The returned TicketTrace is what GET /tickets/{id}/trace returns and
    what the frontend trace-viewer renders.

    Args:
        ticket_id: UUID of the ticket DB record.
        ticket_text: Raw ticket text submitted by the user.
        classification: Classifier agent output.
        retrieved_chunks: All chunks returned by the retriever (ordered by similarity).
        draft: Drafter agent output.
        verdict: Critic agent output.
        entailment_results: List of (chunk, EntailmentResult) pairs for each chunk
            that was entailment-checked. May be empty if check was skipped (e.g.
            denylist short-circuit).
        threshold_used: The E3 confidence threshold that was applied (varies by intent).
        cache_hit: True if the answer came from the semantic cache (Epic F2).
        cached_answer: The cached answer text, if cache_hit is True.

    Returns:
        A fully populated TicketTrace.
    """
    entailment_steps = [
        EntailmentStepTrace(
            chunk_id=chunk.chunk_id,
            chunk_content_preview=chunk.content[:200],
            supported=result.supported,
            reason=result.reason,
        )
        for chunk, result in entailment_results
    ]

    return TicketTrace(
        ticket_id=ticket_id,
        ticket_text=ticket_text,
        # Classifier
        intent=classification.intent,
        category=classification.category,
        classifier_confidence=classification.confidence,
        # Retriever
        retrieved_chunk_ids=[c.chunk_id for c in retrieved_chunks],
        retrieved_chunk_count=len(retrieved_chunks),
        # Cache
        cache_hit=cache_hit,
        cached_answer=cached_answer,
        # Drafter
        draft_answer=draft.answer,
        draft_cited_chunk_ids=draft.cited_chunk_ids,
        draft_confidence=draft.confidence,
        # Critic
        threshold_used=threshold_used,
        entailment_steps=entailment_steps,
        citation_supported=verdict.citation_supported,
        critic_reason=verdict.reason,
        # Final
        decision=verdict.decision,
        final_answer=draft.answer if verdict.decision == "auto_resolve" else None,
    )
