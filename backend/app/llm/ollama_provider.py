import time
import httpx
from pydantic import BaseModel

from app.config import settings
from app.llm.base import LLMProvider, LLMResponse

# Fully offline, zero cost, zero rate limit. Pull a model first: `ollama pull llama3.2:3b`
DEFAULT_MODEL = "llama3.2:3b"


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = settings.ollama_base_url

    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={"model": DEFAULT_MODEL, "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()
        latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResponse(
            text=data.get("message", {}).get("content", ""),
            tokens_in=data.get("prompt_eval_count", 0) or 0,
            tokens_out=data.get("eval_count", 0) or 0,
            cost_usd=0.0,
            latency_ms=latency_ms,
        )
