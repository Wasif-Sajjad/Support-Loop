import time
import google.generativeai as genai
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMProvider, LLMResponse

# Free tier: aistudio.google.com — no card required (verify current daily/RPM limits).
DEFAULT_MODEL = "gemini-1.5-flash"


class GeminiProvider(LLMProvider):
    def __init__(self):
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(DEFAULT_MODEL)

    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        start = time.monotonic()
        prompt = "\n\n".join(f"{m['role']}: {m['content']}" for m in messages)
        resp = await self.model.generate_content_async(prompt)
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            text=resp.text,
            tokens_in=0,   # populate from resp.usage_metadata if needed
            tokens_out=0,
            cost_usd=0.0,  # free tier
            latency_ms=latency_ms,
        )
