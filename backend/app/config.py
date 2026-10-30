from __future__ import annotations
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://ekp_user:ekp_password@localhost:5432/enterprise_rag"

    # Ollama — Local AI
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TIMEOUT: int = 60

    # Cloud AI
    CLOUD_PROVIDER: str = "gemini"  # gemini | openai | anthropic
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    CLOUD_MODEL_NAME: str = "gemini-2.0-flash"
    ENABLE_CLOUD_FALLBACK: bool = True

    # Teammate service URLs
    MCP_SERVER_URL: str = "http://localhost:8001"
    RETRIEVAL_API_URL: str = "http://localhost:8002"
    INGESTION_API_URL: str = "http://localhost:8003"

    # Backend settings
    MAX_CONTEXT_TOKENS: int = 4096
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-me-in-production"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
