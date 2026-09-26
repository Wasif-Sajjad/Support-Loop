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
        max_retries: int = 5,
        base_delay: float = 1.0,
    ):
        self.primary = primary
        self.fallbacks = fallbacks or []
        self.max_retries = max_retries
        self.base_delay = base_delay

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        """Return True only for transient errors worth retrying (rate-limit, server error).

        400 / 401 / 404 errors mean the request itself is broken (bad model name,
        wrong auth, invalid payload) — retrying will never help and wastes quota.
        429 / 500 / 502 / 503 are transient and should be retried with backoff.
        """
        err_str = str(exc).lower()
        # Fast-fail signals: bad request, unauthorized, payment/quota required, or not found
        if any(marker in err_str for marker in ("400", "401", "402", "404", "bad request", "not found", "invalid model", "payment required", "payment_required")):
            for code in ("error code: 400", "error code: 401", "error code: 402", "error code: 404",
                         "status 400", "status 401", "status 402", "status 404",
                         "http 400", "http 401", "http 402", "http 404",
                         "bad request", "invalid model", "model not found",
                         "payment required", "payment_required"):
                if code in err_str:
                    return False
        return True

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

    async def complete(
        self, messages: list[dict], response_schema: type[BaseModel] | None = None
    ) -> LLMResponse:
        """Attempt primary provider with retries, then each fallback in order.

        Non-retryable errors (400/401/404) skip all retries and move immediately
        to the next provider so we don't burn quota on a structurally bad request.
        """
        last_exception: Exception | None = None

        providers = [self.primary] + self.fallbacks
        for provider in providers:
            provider_label = provider.__class__.__name__
            for attempt in range(self.max_retries):
                try:
                    return await self._run_provider(provider, messages, response_schema)
                except Exception as e:
                    last_exception = e
                    if not self._is_retryable(e):
                        logger.error(
                            f"{provider_label}: non-retryable error — skipping all retries: {e}"
                        )
                        break  # move to next provider immediately

                    delay = self.base_delay * (2 ** attempt)
                    err_str = str(e)
                    if "Please try again in" in err_str:
                        try:
                            hint = float(
                                err_str.split("Please try again in")[1].split("s")[0].strip()
                            )
                            delay = max(delay, hint + 0.5)
                        except Exception:
                            pass

                    if attempt < self.max_retries - 1:
                        logger.warning(
                            f"{provider_label} failed (attempt {attempt + 1}/{self.max_retries}): "
                            f"{e}. Retrying in {delay:.1f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"{provider_label} exhausted after {self.max_retries} attempts: {e}"
                        )

        raise RuntimeError("All LLM providers failed") from last_exception


def _instantiate_provider(name: str) -> LLMProvider:
    """Instantiate a named LLM provider by string key.

    Args:
        name: Provider identifier (groq | gemini | cerebras | ollama).

    Returns:
        Concrete LLMProvider instance.
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


def get_provider(name: str) -> LLMProvider:
    """Factory — returns a RetryFallbackProvider wrapping primary → Gemini.

    Fallback chain (when primary is groq):
      1. Groq (primary, max_retries=5)
      2. Gemini (1st fallback, if GEMINI_API_KEY is set)

    Non-retryable errors (400/401/404) skip directly to the next provider.
    Only 429/5xx errors are retried with exponential backoff.

    Args:
        name: Provider identifier from LLM_PROVIDER env var.

    Returns:
        RetryFallbackProvider wrapping the fallback chain.
    """
    from app.config import settings

    primary = _instantiate_provider(name)
    fallbacks: list[LLMProvider] = []

    if name == "groq":
        # 1st fallback: Gemini
        if settings.gemini_api_key:
            try:
                fallbacks.append(_instantiate_provider("gemini"))
                logger.info("Gemini registered as 1st fallback provider.")
            except Exception as e:
                logger.warning(f"Failed to instantiate Gemini fallback: {e}")

    return RetryFallbackProvider(primary=primary, fallbacks=fallbacks)
