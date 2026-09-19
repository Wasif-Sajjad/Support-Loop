"""Epic E — the escalation critic. Combines hard policy rules (deterministic, auditable)
with a confidence floor and a citation-support check (see docs/architecture.md 3.7).
"""
from app.schemas import DraftResolution, ClassificationResult, CriticVerdict
from app.config import settings

# TODO: expand with real categories from docs/architecture.md — this is a starting point.
POLICY_DENYLIST_INTENTS = {"cancel_account", "change_payment_method", "delete_account", "security_breach"}


def escalation_critic(
    classification: ClassificationResult,
    draft: DraftResolution,
) -> CriticVerdict:
    if classification.intent in POLICY_DENYLIST_INTENTS:
        return CriticVerdict(decision="escalate", reason="Policy denylist intent", citation_supported=False)

    if not draft.cited_chunk_ids or draft.confidence < settings.confidence_threshold:
        return CriticVerdict(
            decision="escalate",
            reason=f"Low confidence ({draft.confidence}) or no supporting citation",
            citation_supported=bool(draft.cited_chunk_ids),
        )

    # TODO (Epic E1): replace this stub with a real entailment check — a small LLM call or
    # local NLI model asking "does this citation actually support this claim?"
    citation_supported = True

    if not citation_supported:
        return CriticVerdict(decision="escalate", reason="Citation does not support claim", citation_supported=False)

    return CriticVerdict(decision="auto_resolve", reason="Passed all checks", citation_supported=True)
