"""Runtime configuration. Secrets are injected by the deployment secret manager."""
from functools import lru_cache
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ODEI_", env_file=".env", extra="ignore")
    app_name: str = "ODEI Clinic Management OS API"
    environment: str = Field(default="development", pattern="^(development|test|staging|production)$")
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    mongodb_uri: SecretStr | None = None
    mongodb_database: str = "odei_clinic"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_allowed_algorithms: tuple[str, ...] = ("RS256",)
    oidc_jwks_cache_seconds: int = Field(default=300, ge=30, le=3600)


@lru_cache
def get_settings() -> Settings:
    return Settings()
