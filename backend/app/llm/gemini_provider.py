import time
import google.generativeai as genai
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMProvider, LLMResponse
from app.llm.pricing import calculate_cost

# Free tier: aistudio.google.com — no card required (verify current daily/RPM limits).
DEFAULT_MODEL = "gemini-3.6-flash"


class GeminiProvider(LLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(DEFAULT_MODEL)

    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        start = time.monotonic()
        prompt = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        
        gen_config = None
        if response_schema is not None:
            gen_config = genai.GenerationConfig(response_mime_type="application/json")

        resp = await self.model.generate_content_async(
            prompt,
            generation_config=gen_config,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        # Extract real token usage from Gemini response metadata
        usage = getattr(resp, "usage_metadata", None)
        tokens_in = getattr(usage, "prompt_token_count", 0) or 0
        tokens_out = getattr(usage, "candidates_token_count", 0) or 0

        # Fallback estimation if usage_metadata wasn't provided by SDK
        if tokens_in == 0 and prompt:
            tokens_in = max(1, len(prompt.split()))
        if tokens_out == 0 and resp.text:
            tokens_out = max(1, len(resp.text.split()))

        cost_usd = calculate_cost(DEFAULT_MODEL, tokens_in, tokens_out)
        return LLMResponse(
            text=resp.text,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,  # estimated at standard pricing
            latency_ms=latency_ms,
        )
