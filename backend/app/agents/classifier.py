"""Epic C — classifies a ticket into a Bitext intent/category with a confidence score.
v1 is zero-shot/few-shot prompted (see docs/prd.md FR2) — Project 2 later swaps this
for a fine-tuned model behind the same function signature.
"""
import json
from app.llm.base import LLMProvider
from app.schemas import ClassificationResult

from app.agents.few_shot_examples import FEW_SHOT_EXAMPLES

def format_examples() -> str:
    lines = []
    for ex in FEW_SHOT_EXAMPLES:
        lines.append(f'Example: "{ex["instruction"]}"')
        lines.append(f'-> {{"intent": "{ex["intent"]}", "category": "{ex["category"]}", "confidence": 0.95}}\n')
    return "\n".join(lines)


async def classify_intent(ticket_text: str, llm: LLMProvider) -> ClassificationResult:
    messages = [
        {"role": "system", "content": (
            "You are a support ticket classifier. Given a ticket, return ONLY a JSON object "
            "with keys intent, category, confidence (0-1). Use the Bitext taxonomy. "
            f"Examples:\n{format_examples()}"
        )},
        {"role": "user", "content": ticket_text},
    ]
    response = await llm.complete(messages, response_schema=ClassificationResult)
    data = json.loads(response.text)
    return ClassificationResult(**data)
