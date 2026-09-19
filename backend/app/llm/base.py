"""The one interface every agent must call through — never hit a provider SDK directly
from agent/route code (see AGENTS.md). This is what makes swapping Groq -> Gemini ->
Ollama, or later AWS Bedrock, a config change instead of a rewrite.
"""
from abc import ABC, abstractmethod
from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        """Send messages to the model. If response_schema is given, the provider
        implementation is responsible for returning text that validates against it
        (e.g. via JSON-mode prompting) — validation itself happens in the calling agent.
        """
        raise NotImplementedError


def get_provider(name: str) -> LLMProvider:
    """Factory — routes on the LLM_PROVIDER env var. Add a retry-with-fallback
    wrapper here later (Epic F) so a 429 on the primary falls back automatically.
    """
    if name == "groq":
        from app.llm.groq_provider import GroqProvider
        return GroqProvider()
    if name == "gemini":
        from app.llm.gemini_provider import GeminiProvider
        return GeminiProvider()
    if name == "ollama":
        from app.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    raise ValueError(f"Unknown LLM provider: {name}")
