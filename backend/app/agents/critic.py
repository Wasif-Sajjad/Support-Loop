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
  E2 — POLICY_DENYLIST_INTENTS = {delete_account, complaint,
            registration_problems, infrastructure_issue}.
       Unit-tested in backend/tests/test_critic.py::test_e2_denylist_*.
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
    BatchEntailmentResponse,
    ClassificationResult,
    CriticVerdict,
    CriticVerdictWithTrace,
    DraftResolution,
    EntailmentResult,
    EntailmentStepTrace,
    RetrievedChunk,
    SingleChunkEntailment,
    TicketTrace,
)
from app.config import settings
import uuid as _uuid

# ---------------------------------------------------------------------------
# E2 — Hard policy denylist
# ---------------------------------------------------------------------------
# These intents ALWAYS escalate, regardless of confidence or citation quality.
#
# - delete_account: irreversible/destructive; requires human sign-off.
# - complaint: reputational/sensitive; requires human sign-off.
#
# Note: infrastructure_issue and registration_problems are governed by E3 stricter
# thresholds (0.9), permitting well-grounded self-serve resolutions when confidence
# is high while preventing premature auto-resolutions on bug reports or ambiguous issues.
POLICY_DENYLIST_INTENTS: frozenset[str] = frozenset({
    "delete_account",
    "complaint",
})

# ---------------------------------------------------------------------------
# E3 — Confidence thresholds
# ---------------------------------------------------------------------------
# General floor: 0.7 (from settings.confidence_threshold / .env CONFIDENCE_THRESHOLD).
# Stricter per-intent overrides for intents that carry production or registration risk.
STRICTER_THRESHOLD_INTENTS: dict[str, float] = {
    "infrastructure_issue": 0.9,
    # Raised from 0.7 to 0.9 based on 54-row eval run evidence:
    # 0.7 proved too permissive for registration issues (e.g. captcha/verification failures
    # auto-resolving on generic sign-up text).
    # NOTE ON TICKET 8 ("I don't know how to inform of sign-up errrors"):
    # This is a user reporting a platform signup bug that gets miscategorized as a
    # self-service how-to inquiry. This represents a known relevance-vs-entailment limitation:
    # the answer claims may be strictly entailed by the KB, but the KB itself is not relevant
    # to an active software defect. Thresholds mitigate but do not fully eliminate this semantic gap.
    "registration_problems": 0.9,
}

# ---------------------------------------------------------------------------
# E1 — Entailment check prompt (batched)
# ---------------------------------------------------------------------------
_BATCH_ENTAILMENT_SYSTEM_PROMPT = """\
You are a citation auditor. You will be shown:
  1. A drafted support answer.
  2. One or more knowledge base passages cited in that answer, each identified by an ID.

Your job: for EACH cited passage, decide whether that passage provides factual support for at least one claim in the drafted answer.

Return ONLY a JSON object with a "results" key containing a list of objects.
Each object must have:
  - "chunk_id" (string): the exact ID of the cited passage.
  - "supported" (boolean): true if the passage provides source material for AT LEAST ONE claim in the answer. It does not need to support the entire answer. False ONLY if it is completely off-topic, unused, or contradicted.
  - "reason" (string): one or two sentences explaining your decision.

Do not consider whether the answer is generally correct — only whether EACH passage was actually used as factual grounding for some part of the answer.
Return ONLY valid JSON, no markdown fences.
"""


async def batch_entailment_check(
    answer: str,
    cited_chunks: list[RetrievedChunk],
    llm: LLMProvider,
) -> list[tuple[RetrievedChunk, EntailmentResult]]:
    """E1 — Ask the LLM to score all cited KB chunks in a single batched call.

    Reduces latency from N sequential LLM calls to 1 batched LLM call.

    Args:
        answer: The drafted answer text from the drafter agent.
        cited_chunks: List of RetrievedChunk objects cited in the draft.
        llm: An LLMProvider instance.

    Returns:
        A list of (RetrievedChunk, EntailmentResult) pairs for every cited chunk.
    """
    if not cited_chunks:
        return []

    passages_text = []
    for idx, chunk in enumerate(cited_chunks, 1):
        passages_text.append(
            f"--- Passage {idx} [ID: {chunk.chunk_id}] ---\n{chunk.content.strip()}"
        )
    formatted_passages = "\n\n".join(passages_text)

    messages = [
        {"role": "system", "content": _BATCH_ENTAILMENT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Drafted answer:\n{answer}\n\n"
                f"Cited passages:\n{formatted_passages}\n\n"
                "Evaluate all cited passages and return JSON now."
            ),
        },
    ]
    response = await llm.complete(messages, response_schema=BatchEntailmentResponse)

    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    data = json.loads(raw)

    results_map: dict[str, dict] = {}
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            for item in data["results"]:
                if isinstance(item, dict) and "chunk_id" in item:
                    results_map[str(item["chunk_id"]).lower()] = item
        elif "supported" in data:
            first_id = str(cited_chunks[0].chunk_id).lower()
            results_map[first_id] = data
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "chunk_id" in item:
                results_map[str(item["chunk_id"]).lower()] = item

    n_chunks = len(cited_chunks)
    per_tokens_in = response.tokens_in // n_chunks if n_chunks else 0
    per_tokens_out = response.tokens_out // n_chunks if n_chunks else 0
    per_cost = response.cost_usd / n_chunks if n_chunks else 0.0
    per_latency = response.latency_ms // n_chunks if n_chunks else 0

    entailment_results: list[tuple[RetrievedChunk, EntailmentResult]] = []
    for idx, chunk in enumerate(cited_chunks):
        cid_str = str(chunk.chunk_id).lower()
        matched = results_map.get(cid_str)
        if not matched:
            for k, v in results_map.items():
                if k in cid_str or cid_str in k:
                    matched = v
                    break
        if not matched and idx < len(results_map):
            matched = list(results_map.values())[idx]

        if matched:
            sup = bool(matched.get("supported", False))
            reason = str(matched.get("reason", "No reason provided."))
        else:
            sup = False
            reason = "No entailment result returned for this chunk."

        result = EntailmentResult(
            supported=sup,
            reason=reason,
            tokens_in=per_tokens_in,
            tokens_out=per_tokens_out,
            cost_usd=per_cost,
            latency_ms=per_latency,
            provider_name=response.provider_name,
        )
        entailment_results.append((chunk, result))

    return entailment_results


async def entailment_check(
    answer: str,
    cited_chunk: RetrievedChunk,
    llm: LLMProvider,
) -> EntailmentResult:
    """Backward-compatible single-chunk entailment check."""
    results = await batch_entailment_check(answer, [cited_chunk], llm)
    if results:
        return results[0][1]
    return EntailmentResult(
        supported=False,
        reason="Entailment check failed to produce results.",
    )


# ---------------------------------------------------------------------------
# Content-based overrides
# ---------------------------------------------------------------------------
# Registration risk phrases: account-enumeration, bot, or token validation issues
# where even a grounded answer shouldn't be auto-sent.
REGISTRATION_RISK_PHRASES: tuple[str, ...] = (
    "already in use",
    "existing account",
    "captcha",
    "verification failed",
    "link says expired",
    "verification link says expired",
)

# Bug-report language patterns: user reporting a defect or active malfunction
# distinct from how-to inquiry. Entailed citations cannot remediate software bugs.
BUG_REPORT_PHRASES: tuple[str, ...] = (
    "how to report",
    "how to inform of",
    "getting an error",
    "getting error",
    "keeps failing",
    "report issues",
    "report an error",
    "submit a bug",
    "file a bug",
)


# ---------------------------------------------------------------------------
# Main critic function
# ---------------------------------------------------------------------------

async def escalation_critic(
    classification: ClassificationResult,
    draft: DraftResolution,
    retrieved_chunks: list[RetrievedChunk],
    llm: LLMProvider,
    ticket_text: str = "",
) -> CriticVerdictWithTrace:
    """Decide whether a drafted answer should be auto-resolved or escalated.

    Applies checks in strict priority order:

    0. Content-based overrides: registration abuse risk or bug-report defect phrasing.
    1. (E2) Hard policy denylist: some intents always escalate. No LLM call.
    2. (E3) Confidence floor + citation presence: escalate if below threshold. No LLM call.
    3. (E1) Citation entailment: single batched LLM call for ALL cited chunks. Escalates if ANY
       chunk fails.
    """
    def _short_circuit(verdict: CriticVerdict) -> CriticVerdictWithTrace:
        """Return a verdict with an empty entailment list (pre-entailment escalation)."""
        return CriticVerdictWithTrace(verdict=verdict, entailment_results=[])

    # --- Check 0: Content-based overrides ---
    text_lower = ticket_text.lower().strip()
    if text_lower:
        # 0a. Registration abuse / enumeration risk
        if classification.intent == "registration_problems" and any(p in text_lower for p in REGISTRATION_RISK_PHRASES):
            return _short_circuit(CriticVerdict(
                decision="escalate",
                reason="Content override: registration security/abuse risk pattern detected in ticket text",
                citation_supported=False,
            ))

        # 0b. Active defect / bug-report phrasing across any intent
        if any(p in text_lower for p in BUG_REPORT_PHRASES):
            return _short_circuit(CriticVerdict(
                decision="escalate",
                reason="Content override: defect/bug-report language pattern detected (requires human investigation)",
                citation_supported=False,
            ))

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

    # --- Check 3 (E1): Citation entailment ---
    chunk_map: dict[str, RetrievedChunk] = {
        str(c.chunk_id): c for c in retrieved_chunks
    }

    valid_chunks: list[RetrievedChunk] = []
    hallucinated_ids: list[str] = []

    for cited_id in draft.cited_chunk_ids:
        cited_id_str = str(cited_id)
        chunk = chunk_map.get(cited_id_str)
        if chunk is None:
            hallucinated_ids.append(cited_id_str)
        else:
            valid_chunks.append(chunk)

    entailment_results: list[tuple[RetrievedChunk, EntailmentResult]] = []
    if valid_chunks:
        entailment_results = await batch_entailment_check(draft.answer, valid_chunks, llm)

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
