"""Story D unit tests — Resolution Drafting Agent.

Verification plan (per Epic D spec):
  - D3 path: drafter must return an empty answer and zero confidence when no chunks
    are provided, WITHOUT making an LLM call.
  - D3 path: drafter must also abstain when all chunks fall below MIN_SIMILARITY_THRESHOLD.
  - D2 grounded path: for a ticket whose intent IS KB-backed (recover_password,
    contact_customer_service), drafter must return a non-empty answer with at least
    one cited_chunk_id — proving the agent drafts a grounded, cited response.
  - D2 abstain path: for a ticket whose intent has NO KB content yet (delete_account,
    switch_account), the retriever returns empty → drafter abstains → no hallucination.

Tests marked @pytest.mark.integration make real LLM + DB calls and only run when
INTEGRATION=1 is set in the environment, keeping the default CI suite fast.
"""
import os
import uuid
import pytest

from app.agents.drafter import draft_resolution, MIN_SIMILARITY_THRESHOLD
from app.schemas import DraftResolution, RetrievedChunk


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _chunk(content: str, similarity: float = 0.85) -> RetrievedChunk:
    """Build a fake RetrievedChunk for unit testing without a DB."""
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        content=content,
        similarity=similarity,
    )


# ---------------------------------------------------------------------------
# D3 — Empty-retrieval abstain (no LLM call needed — pure unit tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_d3_abstain_on_empty_chunks() -> None:
    """D3: drafter must return a structured abstain when no chunks are provided."""
    # Pass None as llm — if the function tries to call it, the test will crash,
    # proving that the LLM is NOT called on the empty path.
    result = await draft_resolution("please delete my account", [], llm=None)  # type: ignore[arg-type]

    assert isinstance(result, DraftResolution)
    assert result.answer == "", "answer must be empty string on abstain"
    assert result.cited_chunk_ids == [], "no citations on abstain"
    assert result.confidence == 0.0, "confidence must be 0.0 on abstain"


@pytest.mark.asyncio
async def test_d3_abstain_on_below_threshold_chunks() -> None:
    """D3: drafter must abstain when all chunks fall below MIN_SIMILARITY_THRESHOLD."""
    weak_chunk = _chunk("Some vaguely related content.", similarity=MIN_SIMILARITY_THRESHOLD - 0.01)
    result = await draft_resolution("switch my account to premium", [weak_chunk], llm=None)  # type: ignore[arg-type]

    assert result.answer == ""
    assert result.cited_chunk_ids == []
    assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# D2 — Grounded drafting with real LLM (integration tests)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run (requires LLM API key and seeded KB)",
)
async def test_d2_grounded_answer_recover_password() -> None:
    """D2: for a recover_password ticket with strong KB chunks, drafter must return
    a non-empty answer citing at least one chunk ID — no hallucination, no abstain."""
    from app.llm.base import get_provider
    from app.config import settings

    llm = get_provider(settings.llm_provider)

    # Simulate two chunks from the recover_password KB article.
    chunk_a = _chunk(
        "Go to the sign-in page and click 'Forgot password?' below the password field. "
        "Enter your email and click 'Send reset link'. Check your inbox for the reset email.",
        similarity=0.91,
    )
    chunk_b = _chunk(
        "The password reset link is valid for 60 minutes. If it has expired, start the "
        "process again from the sign-in page.",
        similarity=0.84,
    )

    result = await draft_resolution(
        "where can i retrieve my forgotten account pass",
        [chunk_a, chunk_b],
        llm,
    )

    assert result.answer, "Expected a non-empty answer for a KB-backed ticket"
    assert len(result.cited_chunk_ids) >= 1, "Expected at least one citation"
    assert result.confidence > 0.0, "Expected positive confidence for a KB-backed answer"
    # Cited IDs must be drawn from the chunks we provided — not invented.
    provided_ids = {chunk_a.chunk_id, chunk_b.chunk_id}
    for cid in result.cited_chunk_ids:
        assert cid in provided_ids, f"Cited ID {cid} was not in the provided chunks — hallucination!"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run (requires LLM API key and seeded KB)",
)
async def test_d2_grounded_answer_contact_customer_service() -> None:
    """D2: for a contact_customer_service ticket with a strong KB chunk, drafter
    must return a non-empty, cited answer."""
    from app.llm.base import get_provider
    from app.config import settings

    llm = get_provider(settings.llm_provider)

    chunk = _chunk(
        "We offer live chat (Monday–Friday, 9 AM–6 PM UTC+5), email at support@example.com "
        "with a 24-hour response time, and a Help Center at help.example.com available 24/7.",
        similarity=0.88,
    )

    result = await draft_resolution(
        "need to see what hours i can reach customer support",
        [chunk],
        llm,
    )

    assert result.answer
    assert result.cited_chunk_ids == [chunk.chunk_id], (
        "Drafter should cite exactly the one chunk we provided"
    )
    assert result.confidence > 0.0


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="Integration test — set INTEGRATION=1 to run (requires LLM API key and seeded KB)",
)
async def test_d2_abstain_for_no_kb_content_intent() -> None:
    """D2 / NFR4: for an intent with no KB content (delete_account), the retriever
    returns empty and the drafter must abstain — it must NOT hallucinate an answer."""
    from app.llm.base import get_provider
    from app.config import settings

    llm = get_provider(settings.llm_provider)

    # Simulate the retriever returning no relevant chunks for delete_account.
    result = await draft_resolution(
        "how can i remove a platinum account",
        chunks=[],
        llm=llm,
    )

    assert result.answer == "", (
        "Drafter must return empty answer when no KB content is available — "
        "not hallucinate an account-deletion procedure."
    )
    assert result.cited_chunk_ids == []
    assert result.confidence == 0.0
