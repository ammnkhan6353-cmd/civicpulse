"""Application settings, read from environment variables (12-factor).

Nothing secret has a real default here: the API key and database password come
from .env (Compose), a Kubernetes Secret, or GitHub Secrets - never from the repo.
"""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_name: str = "CivicPulse"
    log_level: str = "INFO"

    # --- Database -----------------------------------------------------------
    # Either give a full DATABASE_URL, or the individual POSTGRES_* parts
    # (Kubernetes passes the parts: host/db/user from a ConfigMap, password from a Secret).
    database_url: str | None = None
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "civicpulse"
    postgres_user: str = "civicpulse"
    postgres_password: SecretStr = SecretStr("")

    # --- Redis --------------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # --- Triage -------------------------------------------------------------
    triage_provider: str = "llm"  # llm | ollama | rules | simulated
    triage_timeout_seconds: float = 10.0
    triage_cache_ttl_seconds: int = 24 * 60 * 60
    groq_api_key: SecretStr = SecretStr("")
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "llama-3.1-8b-instant"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.2:1b"
    simulated_failure_mode: str = "none"  # none | raise | malformed

    # --- Cache and rate limiting ---------------------------------------------
    stats_cache_ttl_seconds: int = 30
    rate_limit_per_minute: int = Field(default=20, ge=1)  # shared CGNAT IPs need burst room

    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
