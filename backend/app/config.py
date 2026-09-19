from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — all values come from environment variables / .env file.

    Add new provider keys here when a new LLMProvider adapter is created so that
    `settings` stays the single source of truth for all external credentials.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore unknown env vars so adding a new key to .env never crashes startup.
        extra="ignore",
    )

    # --- Database ---
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ticket_triage"
    redis_url: str = "redis://localhost:6379/0"

    # --- LLM providers ---
    llm_provider: str = "groq"  # groq | gemini | cerebras | cloudflare | ollama
    groq_api_key: str = ""
    gemini_api_key: str = ""
    cerebras_api_key: str = ""
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""
    ollama_base_url: str = "http://localhost:11434"

    # --- Embeddings ---
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Observability (optional, self-hosted Langfuse) ---
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # --- Critic thresholds ---
    # E3: PROVISIONAL DEFAULT — do not tune until eval_set ≥ 50 rows and KB coverage complete.
    # See backend/app/agents/critic.py and docs/eval_set_README.md for context.
    confidence_threshold: float = 0.7

    # --- App ---
    environment: str = "development"


settings = Settings()

