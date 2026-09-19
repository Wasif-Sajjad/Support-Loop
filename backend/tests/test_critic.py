"""Story E unit tests — Escalation Critic.

Test coverage by story:
  E1 — Adversarial entailment check: a ticket whose top-retrieved chunk is
       topically similar but does NOT answer the question. Asserts the critic
       escalates with citation_supported=False.
       (Integration — requires INTEGRATION=1 and a live LLM key)

  E2 — Denylist: pure unit tests, no LLM required.
       test_e2_denylist_delete_account  — delete_account always escalates.
       test_e2_denylist_complaint       — complaint always escalates.
       test_e2_non_denylist_passes_denylist_check — recover_password is not denylisted.

  E3 — Threshold unit tests: pure, no LLM.
       test_e3_low_confidence_escalates  — confidence below 0.7 floor escalates.
       test_e3_infra_strict_threshold    — infrastructure_issue requires ≥ 0.9.
       test_e3_infra_high_confidence_ok  — infra at 0.91 passes threshold check
                                           (entailment still runs in integration).
"""
import uuid
import pytest

from app.agents.critic import (
    escalation_critic,
    entailment_check,
    POLICY_DENYLIST_INTENTS,
    STRICTER_THRESHOLD_INTENTS,
)
from app.schemas import (
    ClassificationResult,
    CriticVerdict,
    DraftResolution,
    EntailmentResult,
    RetrievedChunk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classification(intent: str, category: str = "ACCOUNT", confidence: float = 0.9) -> ClassificationResult:
    return ClassificationResult(intent=intent, category=category, confidence=confidence)


def _draft(
    answer: str = "Here is how you reset your password.",
    chunk_ids: list[uuid.UUID] | None = None,
    confidence: float = 0.85,
) -> DraftResolution:
    if chunk_ids is None:
        chunk_ids = [uuid.uuid4()]
    return DraftResolution(answer=answer, cited_chunk_ids=chunk_ids, confidence=confidence)


def _chunk(content: str, chunk_id: uuid.UUID | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        content=content,
        similarity=0.85,
    )


# ---------------------------------------------------------------------------
# E2 — Denylist (pure unit tests — no LLM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e2_denylist_delete_account() -> None:
    """E2: delete_account intent must always escalate, regardless of confidence."""
    chunk = _chunk("You can delete your account from account settings.")
    cid = chunk.chunk_id
    draft = _draft(
        answer="Go to settings and click Delete Account.",
        chunk_ids=[cid],
        confidence=0.99,  # even sky-high confidence must escalate
    )
    verdict = await escalation_critic(
        _classification("delete_account"),
        draft,
        retrieved_chunks=[chunk],
        llm=None,  # type: ignore[arg-type]  — must NOT be called for denylist check
    )
    assert verdict.decision == "escalate"
    assert "denylist" in verdict.reason.lower()
    assert verdict.citation_supported is False


@pytest.mark.asyncio
async def test_e2_denylist_complaint() -> None:
    """E2: complaint intent must always escalate."""
    chunk = _chunk("We value your feedback and take all complaints seriously.")
    cid = chunk.chunk_id
    draft = _draft(
        answer="Your complaint has been noted.",
        chunk_ids=[cid],
        confidence=0.95,
    )
    verdict = await escalation_critic(
        _classification("complaint", category="FEEDBACK"),
        draft,
        retrieved_chunks=[chunk],
        llm=None,  # type: ignore[arg-type]
    )
    assert verdict.decision == "escalate"
    assert "denylist" in verdict.reason.lower()


@pytest.mark.asyncio
async def test_e2_non_denylist_intent_not_blocked_by_denylist() -> None:
    """E2: recover_password is NOT in the denylist — should not escalate at step 1."""
    assert "recover_password" not in POLICY_DENYLIST_INTENTS
    # We don't assert the final decision here (entailment step needs a real LLM).
    # This just verifies the denylist set is correct.


# ---------------------------------------------------------------------------
# E3 — Confidence thresholds (pure unit tests — no LLM)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_e3_low_confidence_escalates() -> None:
    """E3: confidence below the 0.7 default floor must escalate."""
    chunk = _chunk("Reset your password via the forgot-password link.")
    cid = chunk.chunk_id
    draft = _draft(chunk_ids=[cid], confidence=0.5)
    verdict = await escalation_critic(
        _classification("recover_password"),
        draft,
        retrieved_chunks=[chunk],
        llm=None,  # type: ignore[arg-type]
    )
    assert verdict.decision == "escalate"
    assert "0.50" in verdict.reason or "threshold" in verdict.reason.lower()


@pytest.mark.asyncio
async def test_e3_infra_strict_threshold_escalates_at_low_conf() -> None:
    """E3: infrastructure_issue requires ≥ 0.9. Confidence of 0.85 must escalate."""
    assert STRICTER_THRESHOLD_INTENTS["infrastructure_issue"] == 0.9
    chunk = _chunk("Run kubectl describe pod <name> to see events.")
    cid = chunk.chunk_id
    draft = _draft(
        answer="Run kubectl describe pod to diagnose the issue.",
        chunk_ids=[cid],
        confidence=0.85,  # above default 0.7 but below infra's 0.9
    )
    verdict = await escalation_critic(
        _classification("infrastructure_issue", category="INFRA"),
        draft,
        retrieved_chunks=[chunk],
        llm=None,  # type: ignore[arg-type]
    )
    assert verdict.decision == "escalate"


@pytest.mark.asyncio
async def test_e3_no_citations_escalates() -> None:
    """E3: drafter with no cited_chunk_ids must escalate regardless of confidence."""
    draft = _draft(answer="Reset password via the link.", chunk_ids=[], confidence=0.9)
    verdict = await escalation_critic(
        _classification("recover_password"),
        draft,
        retrieved_chunks=[],
        llm=None,  # type: ignore[arg-type]
    )
    assert verdict.decision == "escalate"
    assert verdict.citation_supported is False


# ---------------------------------------------------------------------------
# E1 — Adversarial entailment (integration test — requires INTEGRATION=1)
# ---------------------------------------------------------------------------

import os

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run (requires LLM API key)",
)
async def test_e1_adversarial_entailment_wrong_chunk() -> None:
    """E1: A create_account ticket is answered, but the ONLY cited chunk is from
    recover_password.md — topically similar (account management) but does NOT
    support the create_account answer. The critic must escalate with
    citation_supported=False.

    This is the key adversarial case: it proves the entailment check catches
    semantic drift that a simple cosine-similarity score would miss.
    """
    from app.llm.base import get_provider
    from app.config import settings

    llm = get_provider(settings.llm_provider)

    # The KB chunk is from recover_password.md — totally real content, but wrong intent.
    misleading_chunk = _chunk(
        content=(
            "Go to the sign-in page and click 'Forgot password?' below the password field. "
            "Enter your email and click 'Send reset link'. Check your inbox for the reset email. "
            "The link is valid for 60 minutes."
        ),
    )

    # The drafter (incorrectly) cites this chunk to answer a create_account ticket.
    draft = _draft(
        answer=(
            "To create a new account, click 'Sign up' on the homepage, enter your name "
            "and email, choose a password, and click 'Create account'."
        ),
        chunk_ids=[misleading_chunk.chunk_id],
        confidence=0.88,
    )

    verdict = await escalation_critic(
        _classification("create_account"),
        draft,
        retrieved_chunks=[misleading_chunk],
        llm=llm,
    )

    assert verdict.decision == "escalate", (
        "Critic should escalate because the cited chunk (recover_password) does not "
        "support the create_account answer — even though the confidence is high."
    )
    assert verdict.citation_supported is False, (
        "citation_supported must be False when the entailment check fails."
    )


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run (requires LLM API key)",
)
async def test_e1_entailment_passes_for_correct_chunk() -> None:
    """E1: A recover_password ticket with a correctly cited recover_password chunk
    must pass the entailment check and return auto_resolve."""
    from app.llm.base import get_provider
    from app.config import settings

    llm = get_provider(settings.llm_provider)

    correct_chunk = _chunk(
        content=(
            "Go to the sign-in page and click 'Forgot password?' below the password field. "
            "Enter your email and click 'Send reset link'. Check your inbox for the reset email."
        ),
    )
    draft = _draft(
        answer=(
            "To reset your password, go to the sign-in page and click 'Forgot password?'. "
            "Enter your email to receive a reset link."
        ),
        chunk_ids=[correct_chunk.chunk_id],
        confidence=0.91,
    )

    verdict = await escalation_critic(
        _classification("recover_password"),
        draft,
        retrieved_chunks=[correct_chunk],
        llm=llm,
    )

    assert verdict.decision == "auto_resolve"
    assert verdict.citation_supported is True


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run (requires LLM API key)",
)
async def test_e1_entailment_check_direct() -> None:
    """E1: Direct unit test for entailment_check() in isolation.
    Verifies the function returns an EntailmentResult with a boolean and reason."""
    from app.llm.base import get_provider
    from app.config import settings

    llm = get_provider(settings.llm_provider)

    chunk = _chunk("Click 'Forgot password?' to receive a reset link via email.")
    result = await entailment_check(
        answer="To reset your password, use the 'Forgot password?' link on the login page.",
        cited_chunk=chunk,
        llm=llm,
    )

    assert isinstance(result, EntailmentResult)
    assert isinstance(result.supported, bool)
    assert isinstance(result.reason, str)
    assert len(result.reason) > 5
