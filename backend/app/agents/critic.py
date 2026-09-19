"""Epic E — the escalation critic. Combines hard policy rules (deterministic, auditable)
with a confidence floor and a citation-support check (see docs/architecture.md 3.7).

Denylist updated to match the actual project scope (docs/eval_set.csv):
  - delete_account and complaint always escalate regardless of confidence.
  - infrastructure_issue is NOT hard-denylisted — it defaults to escalate via the
    confidence floor instead, so a very high-confidence KB match can still auto-resolve.
    It gets a stricter threshold (0.9) because production infra carries higher risk.
"""
from app.schemas import DraftResolution, ClassificationResult, CriticVerdict
from app.config import settings

# These intents always escalate, no matter how confident the drafter is.
# - delete_account: irreversible/destructive action, requires human sign-off.
# - complaint: reputational/sensitive, requires human sign-off.
POLICY_DENYLIST_INTENTS: frozenset[str] = frozenset({"delete_account", "complaint"})

# Intents that are allowed to auto-resolve but must clear a higher bar than the
# default settings.confidence_threshold due to production risk.
STRICTER_THRESHOLD_INTENTS: dict[str, float] = {
    "infrastructure_issue": 0.9,
}


def escalation_critic(
    classification: ClassificationResult,
    draft: DraftResolution,
) -> CriticVerdict:
    """Decide whether a drafted answer should be auto-resolved or escalated.

    Applies checks in priority order:
      1. Hard policy denylist (always escalate regardless of confidence).
      2. Confidence floor + citation presence check (escalate if below threshold or no citations).
      3. Citation entailment stub (always passes in v1 — see TODO below).

    Args:
        classification: The output of the classifier agent (intent, category, confidence).
        draft: The output of the drafter agent (answer, cited_chunk_ids, confidence).

    Returns:
        A CriticVerdict with decision ('auto_resolve' | 'escalate'), reason, and citation_supported.
    """
    # --- Check 1: Hard policy denylist ---
    if classification.intent in POLICY_DENYLIST_INTENTS:
        return CriticVerdict(
            decision="escalate",
            reason=f"Policy denylist: intent '{classification.intent}' always requires human review",
            citation_supported=False,
        )

    # --- Check 2: Confidence floor + citation presence ---
    threshold = STRICTER_THRESHOLD_INTENTS.get(classification.intent, settings.confidence_threshold)
    if not draft.cited_chunk_ids or draft.confidence < threshold:
        return CriticVerdict(
            decision="escalate",
            reason=(
                f"Confidence {draft.confidence:.2f} below threshold {threshold} "
                f"or no supporting citation"
            ),
            citation_supported=bool(draft.cited_chunk_ids),
        )

    # --- Check 3: Citation entailment (stub — Epic E1) ---
    # TODO (Epic E1): replace this stub with a real entailment check — a small LLM call or
    # local NLI model asking "does this citation actually support this claim?"
    citation_supported = True

    if not citation_supported:
        return CriticVerdict(
            decision="escalate",
            reason="Citation does not semantically support the drafted answer",
            citation_supported=False,
        )

    return CriticVerdict(decision="auto_resolve", reason="Passed all checks", citation_supported=True)

