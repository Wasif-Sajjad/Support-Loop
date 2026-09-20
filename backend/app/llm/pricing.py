"""Standard pricing rates for LLM providers (published commercial rates).

All costs are calculated based on published standard API rates per 1,000 tokens.
NOTE: We operate on free tiers with $0 actual spend; all calculated costs
represent "estimated standard pricing" for capacity and cost-modeling purposes.
"""
from typing import TypedDict


class ModelPricing(TypedDict):
    input_per_1k: float   # USD per 1,000 input tokens
    output_per_1k: float  # USD per 1,000 output tokens


# Standard published pricing table (per 1K tokens)
# Groq: Llama 3.3 70B ($0.59/1M prompt, $0.79/1M completion)
# Gemini 1.5 Flash: ($0.075/1M prompt, $0.30/1M completion)
PRICING_TABLE: dict[str, ModelPricing] = {
    # Groq models
    "groq": {
        "input_per_1k": 0.00059,
        "output_per_1k": 0.00079,
    },
    "llama-3.3-70b-versatile": {
        "input_per_1k": 0.00059,
        "output_per_1k": 0.00079,
    },
    "openai/gpt-oss-120b": {
        "input_per_1k": 0.00059,
        "output_per_1k": 0.00079,
    },
    # Gemini models
    "gemini": {
        "input_per_1k": 0.000075,
        "output_per_1k": 0.00030,
    },
    "gemini-1.5-flash": {
        "input_per_1k": 0.000075,
        "output_per_1k": 0.00030,
    },
    "gemini-3.6-flash": {
        "input_per_1k": 0.000075,
        "output_per_1k": 0.00030,
    },
    # Local / Ollama models
    "ollama": {
        "input_per_1k": 0.0,
        "output_per_1k": 0.0,
    },
}

COST_DISCLAIMER = "estimated at standard pricing"


def calculate_cost(provider_or_model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate estimated cost in USD based on published token pricing.

    Args:
        provider_or_model: Identifier for the model or provider (e.g. "groq", "gemini").
        tokens_in: Count of prompt / input tokens.
        tokens_out: Count of completion / output tokens.

    Returns:
        Estimated cost in USD rounded to 8 decimal places.
    """
    key = provider_or_model.lower()
    rates = PRICING_TABLE.get(key)
    if not rates:
        for k, v in PRICING_TABLE.items():
            if k in key:
                rates = v
                break

    if not rates:
        return 0.0

    in_cost = (tokens_in / 1000.0) * rates["input_per_1k"]
    out_cost = (tokens_out / 1000.0) * rates["output_per_1k"]
    return round(in_cost + out_cost, 8)
