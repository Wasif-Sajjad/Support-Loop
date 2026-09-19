import time
from groq import AsyncGroq
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMProvider, LLMResponse

# Free tier: console.groq.com — no card required, ~30 req/min on Llama 3.3 70B (verify current limits).
DEFAULT_MODEL = "llama-3.3-70b-versatile"


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
        return LLMResponse(
            text=resp.choices[0].message.content,
            tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
            tokens_out=getattr(usage, "completion_tokens", 0) or 0,
            cost_usd=0.0,  # free tier
            latency_ms=latency_ms,
        )
