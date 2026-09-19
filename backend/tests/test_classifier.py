"""Story C3 — unit tests for the classifier agent.

Uses backend/tests/fixtures/classifier_holdout.csv as the test dataset.
This file is confirmed to have ZERO row overlap with:
  - backend/app/agents/few_shot_examples.py (used in the classifier prompt)
  - docs/eval_set.csv (used by the Epic H CI gate)

This separation prevents data leakage between the unit test and the golden eval gate.
"""
import os
import csv
import pytest
from app.agents.classifier import classify_intent, VALID_INTENTS
from app.llm.base import get_provider


def _holdout_path() -> str:
    """Resolve path to the holdout fixture, robust to both local and Docker execution."""
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(tests_dir, "fixtures", "classifier_holdout.csv")


def _load_holdout() -> list[dict]:
    """Load the holdout CSV and return a list of row dicts."""
    path = _holdout_path()
    assert os.path.exists(path), (
        f"classifier_holdout.csv not found at {path}. "
        "Run from the backend/ directory or the repo root."
    )
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


@pytest.mark.asyncio
async def test_classifier_returns_valid_schema() -> None:
    """Classifier must return a ClassificationResult that matches the Pydantic schema."""
    llm = get_provider("groq")
    rows = _load_holdout()
    # Sample 3 rows to keep CI fast and avoid rate-limit hits.
    sample = rows[:3]

    for row in sample:
        ticket_text: str = row["ticket_text"]
        result = await classify_intent(ticket_text, llm)

        assert result.intent, f"intent must be non-empty for: {ticket_text}"
        assert result.category, f"category must be non-empty for: {ticket_text}"
        assert 0.0 <= result.confidence <= 1.0, (
            f"confidence {result.confidence} out of [0, 1] for: {ticket_text}"
        )


@pytest.mark.asyncio
async def test_classifier_uses_valid_intents() -> None:
    """Classifier output intent must always be one of the controlled VALID_INTENTS."""
    llm = get_provider("groq")
    rows = _load_holdout()
    sample = rows[:3]

    for row in sample:
        ticket_text: str = row["ticket_text"]
        result = await classify_intent(ticket_text, llm)

        assert result.intent in VALID_INTENTS, (
            f"Classifier returned unknown intent '{result.intent}' for ticket: {ticket_text!r}. "
            f"Valid intents are: {sorted(VALID_INTENTS)}"
        )


@pytest.mark.asyncio
async def test_classifier_all_intents_covered() -> None:
    """Sanity check: every intent in the holdout fixture is in VALID_INTENTS.

    If this fails, a new intent was added to the holdout without updating few_shot_examples.py.
    """
    rows = _load_holdout()
    holdout_intents = {row["correct_intent"] for row in rows}
    unknown = holdout_intents - VALID_INTENTS
    assert not unknown, (
        f"Holdout contains intents not in VALID_INTENTS: {unknown}. "
        "Add matching examples to few_shot_examples.py."
    )

