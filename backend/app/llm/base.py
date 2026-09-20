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
    provider_name: str = "unknown"


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        """Send messages to the model. If response_schema is given, the provider
        implementation is responsible for returning text that validates against it
        (e.g. via JSON-mode prompting) — validation itself happens in the calling agent.
        """
        raise NotImplementedError


import asyncio
import logging

logger = logging.getLogger(__name__)

from langfuse import observe, get_client
langfuse_client = get_client()

class RetryFallbackProvider(LLMProvider):
    """Wraps a primary provider and an optional list of fallback providers.
    
    Retries the primary provider up to `max_retries` times with exponential backoff.
    If all retries fail, attempts the fallback providers in order.
    """
    def __init__(
        self, 
        primary: LLMProvider, 
        fallbacks: list[LLMProvider] | None = None, 
        max_retries: int = 3, 
        base_delay: float = 2.0
    ):
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.max_retries = max_retries
        self.base_delay = base_delay

    @observe(as_type="generation")
    async def _run_provider(self, provider: LLMProvider, messages: list[dict], response_schema: type[BaseModel] | None) -> LLMResponse:
        provider_name = provider.__class__.__name__.replace("Provider", "").lower()
        # Best practice: Explicitly set input and model name so we don't leak `self` or other kwargs.
        langfuse_client.update_current_generation(
            name=provider.__class__.__name__,
            model=provider.__class__.__name__,
            input=messages,
        )
        response = await provider.complete(messages, response_schema)
        response.provider_name = provider_name
        langfuse_client.update_current_generation(
            output=response.text,
            usage_details={"input": response.tokens_in, "output": response.tokens_out},
            metadata={
                "cost_usd_est": response.cost_usd,
                "pricing_label": "estimated at standard pricing",
                "provider": provider_name,
            }
        )
        return response

    async def complete(self, messages: list[dict], response_schema: type[BaseModel] | None = None) -> LLMResponse:
        last_exception = None
        
        # Try primary with retries
        for attempt in range(self.max_retries):
            try:
                return await self._run_provider(self.primary, messages, response_schema)
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"LLM primary provider failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"LLM primary provider failed after {self.max_retries} attempts: {e}")

        # Try fallbacks if any
        for fallback in self.fallbacks:
            logger.info(f"Attempting fallback to provider: {fallback.__class__.__name__}")
            try:
                return await self._run_provider(fallback, messages, response_schema)
            except Exception as e:
                last_exception = e
                logger.error(f"Fallback provider {fallback.__class__.__name__} failed: {e}")

        raise RuntimeError("All LLM providers failed") from last_exception


def _instantiate_provider(name: str) -> LLMProvider:
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


def get_provider(name: str) -> LLMProvider:
    """Factory — routes on the LLM_PROVIDER env var. Wraps the primary provider
    in a RetryFallbackProvider so API failures (like 429s) are retried automatically.
    """
    from app.config import settings

    primary = _instantiate_provider(name)
    fallbacks = []

    # If using Groq and a Gemini key is available, add Gemini as a fallback
    if name == "groq" and settings.gemini_api_key:
        try:
            fallbacks.append(_instantiate_provider("gemini"))
        except Exception as e:
            logger.warning(f"Failed to instantiate Gemini fallback: {e}")

    return RetryFallbackProvider(primary=primary, fallbacks=fallbacks)
