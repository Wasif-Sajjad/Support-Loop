from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ticket_triage"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "groq"  # groq | gemini | ollama
    groq_api_key: str = ""
    gemini_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"

    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    confidence_threshold: float = 0.7
    environment: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
