"""Application configuration."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    database_url: str = "postgresql+psycopg2://deals:deals@postgres:5432/deals"
    sec_user_agent: str = "DealsPlatformPoC admin@example.com"

    anthropic_api_key: str | None = None
    anthropic_model_extract: str = "claude-haiku-4-5-20251001"
    anthropic_model_synth: str = "claude-sonnet-4-6"

    fred_api_key: str | None = None
    companies_house_api_key: str | None = None

    offline_mode: bool = False
    critic_pass_threshold: float = 0.7
    critic_max_retries: int = 2
    calibration_enabled: bool = False
    enable_scheduler: bool = True

    fixtures_dir: str = "/app/fixtures"
    upload_dir: str = "/app/data/uploads"

    cors_origins: str = "http://localhost:3001,http://frontend:3001"

    @property
    def live_llm(self) -> bool:
        return bool(self.anthropic_api_key) and not self.offline_mode


@lru_cache
def get_settings() -> Settings:
    return Settings()
