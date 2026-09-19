"""Epic C — classifies a ticket into an intent/category with a confidence score.
v1 is zero-shot/few-shot prompted (see docs/prd.md FR2) — Project 2 later swaps this
for a fine-tuned model behind the same function signature.

Intent scope (10 total):
  - 9 real Bitext intents (account/access category): recover_password, create_account,
    delete_account, edit_account, switch_account, registration_problems,
    contact_human_agent, contact_customer_service, complaint.
  - 1 author-curated intent: infrastructure_issue (Bitext has no infra/technical
    category — examples are hand-written in few_shot_examples.py).

VALID_INTENTS is derived from FEW_SHOT_EXAMPLES at import time so the prompt and the
holdout test always use exactly the same controlled vocabulary.
"""
import json

from app.llm.base import LLMProvider
from app.schemas import ClassificationResult
from app.agents.few_shot_examples import FEW_SHOT_EXAMPLES

# Derive the controlled vocabulary from the prompt examples so the two never drift.
VALID_INTENTS: frozenset[str] = frozenset(ex["intent"] for ex in FEW_SHOT_EXAMPLES)


def _format_examples() -> str:
    """Format FEW_SHOT_EXAMPLES into a numbered, human-readable block for the system prompt."""
    lines = []
    for ex in FEW_SHOT_EXAMPLES:
        lines.append(
            f'Example: "{ex["instruction"]}"\n'
            f'-> {{"intent": "{ex["intent"]}", "category": "{ex["category"]}", '
            f'"confidence": {ex["confidence"]}}}'
        )
    return "\n\n".join(lines)


async def classify_intent(ticket_text: str, llm: LLMProvider) -> ClassificationResult:
    """Classify a support ticket into an intent, category, and confidence score.

    Args:
        ticket_text: The raw support ticket text submitted by the user.
        llm: An LLMProvider instance (must be obtained via app.llm.base.get_provider).

    Returns:
        A ClassificationResult with intent, category, and confidence (0-1).

    Raises:
        ValueError: If the LLM returns a response that does not conform to ClassificationResult.
        json.JSONDecodeError: If the LLM response is not valid JSON.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are a support ticket classifier. Given a support ticket, return ONLY a "
                "JSON object with exactly three keys:\n"
                "  - intent (string): one of the valid intents listed below\n"
                "  - category (string): the parent category for that intent\n"
                "  - confidence (float between 0.0 and 1.0)\n\n"
                f"Valid intents: {', '.join(sorted(VALID_INTENTS))}\n\n"
                f"Examples:\n{_format_examples()}\n\n"
                "Return ONLY valid JSON. No explanations, no markdown fences."
            ),
        },
        {"role": "user", "content": ticket_text},
    ]
    response = await llm.complete(messages, response_schema=ClassificationResult)
    data = json.loads(response.text)
    return ClassificationResult(**data)
