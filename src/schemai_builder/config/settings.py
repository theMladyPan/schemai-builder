"""Service settings loaded from environment and .env (pydantic-settings skill pattern)."""

from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogfireSettings(BaseModel):
    """Logfire telemetry group; env name LOGFIRE_TOKEN via one-split nesting."""

    token: SecretStr | None = Field(default=None, description="Logfire write token.")

    @field_validator("token", mode="before")
    @classmethod
    def parse_blank_token_as_none(cls, raw_value: object) -> object:
        """Treat a blank token as unset so tests can silence sending."""
        if isinstance(raw_value, str) and raw_value.strip() == "":
            return None
        return raw_value

    @property
    def token_value(self) -> str | None:
        """Raw token for callers that need the secret itself."""
        return self.token.get_secret_value() if self.token else None


class Settings(BaseSettings):
    """Root settings; env vars split once on underscore (LOGFIRE_TOKEN -> logfire.token)."""

    project: str = Field(default="schemai", description="Service name for telemetry.")
    environment: str = Field(default="local", description="Deployment environment tag.")
    debug: bool = Field(default=False, description="Debug disables logfire scrubbing.")
    logfire: LogfireSettings = Field(default_factory=LogfireSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="_",
        env_nested_max_split=1,
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings for runtime boundaries."""
    return Settings()
