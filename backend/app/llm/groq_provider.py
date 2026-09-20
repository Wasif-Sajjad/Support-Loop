import time
from groq import AsyncGroq
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMProvider, LLMResponse
from app.llm.pricing import calculate_cost

# Available free-tier models on Groq (as of 2026-09):
#   openai/gpt-oss-120b   ← best quality, free
#   openai/gpt-oss-20b    ← faster, lighter
#   qwen/qwen3.8-27b      ← alternative
#   groq/compound         ← compound model
# Update DEFAULT_MODEL here if Groq retires a model.
DEFAULT_MODEL = "openai/gpt-oss-120b"


class GroqProvider(LLMProvider):
    def __init__(self):
        self.client = AsyncGroq(api_key=settings.groq_api_key)

    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        start = time.monotonic()
        kwargs = {}
        if response_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self.client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            **kwargs,
        )
        latency_ms = int((time.monotonic() - start) * 1000)
        usage = resp.usage
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        cost_usd = calculate_cost(DEFAULT_MODEL, tokens_in, tokens_out)
        return LLMResponse(
            text=resp.choices[0].message.content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,  # estimated at standard pricing
            latency_ms=latency_ms,
        )
