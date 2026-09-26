"""
Application configuration loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Smart Developer Onboarding Assistant"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Server ───────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── LLM / OpenAI ─────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_max_tokens: int = 4096
    openai_temperature: float = 0.3

    # ── LLM / Groq ────────────────────────────────────────────────────────────
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-20b"
    groq_max_tokens: int = 4096
    groq_temperature: float = 0.3

    # ── Repository Analysis ───────────────────────────────────────────────────
    # Temporary directory used when cloning remote repos
    clone_base_dir: str = "/tmp/onboarding_repos"
    # Hard limit on total characters sent to LLM from source files
    max_context_chars: int = 40_000

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton pattern for FastAPI DI)."""
    return Settings()
