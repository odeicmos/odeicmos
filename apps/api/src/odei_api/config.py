"""Runtime configuration. Secret values must be injected by the runtime secret manager."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ODEI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ODEI Clinic Management OS API"
    environment: str = Field(default="development", pattern="^(development|test|staging|production)$")
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    mongodb_uri: SecretStr | None = None
    mongodb_database: str = "odei_clinic"


@lru_cache
def get_settings() -> Settings:
    return Settings()
