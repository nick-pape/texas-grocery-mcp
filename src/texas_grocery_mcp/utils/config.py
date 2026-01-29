"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # HEB Configuration
    heb_default_store: str | None = Field(
        default=None,
        description="Default HEB store ID for operations",
    )
    heb_graphql_url: str = Field(
        default="https://www.heb.com/graphql",
        description="HEB GraphQL API endpoint",
    )

    # Auth State
    auth_state_path: Path = Field(
        default=Path("~/.texas-grocery-mcp/auth.json").expanduser(),
        description="Path to Playwright auth state file",
    )

    # Redis Configuration
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL for caching",
    )

    # Observability
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )

    # Reliability
    retry_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of retry attempts for failed requests",
    )
    circuit_breaker_threshold: int = Field(
        default=5,
        ge=1,
        description="Failures before circuit breaker opens",
    )
    circuit_breaker_timeout: int = Field(
        default=30,
        ge=5,
        description="Seconds before circuit breaker attempts recovery",
    )

    def model_post_init(self, __context) -> None:
        """Ensure auth state path is expanded."""
        if "~" in str(self.auth_state_path):
            object.__setattr__(
                self, "auth_state_path", Path(str(self.auth_state_path)).expanduser()
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
