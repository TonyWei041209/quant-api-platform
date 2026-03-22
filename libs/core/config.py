"""Application configuration via pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_user: str = "quant"
    postgres_password: str = "quant_dev_password"
    postgres_db: str = "quant_platform"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # App
    app_env: str = "development"
    app_log_level: str = "INFO"

    # Data sources
    sec_user_agent: str = ""
    openfigi_api_key: str = ""
    massive_api_key: str = ""
    fmp_api_key: str = ""
    bea_api_key: str = ""
    bls_api_key: str = ""
    treasury_api_base_url: str = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"

    # Trade 212
    t212_api_key: str = ""
    t212_api_secret: str = ""
    t212_demo_base_url: str = "https://demo.trading212.com/api/v0"
    t212_live_base_url: str = "https://live.trading212.com/api/v0"
    feature_t212_live_submit: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
