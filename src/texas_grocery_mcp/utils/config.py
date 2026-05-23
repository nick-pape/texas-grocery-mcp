"""Configuration management using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

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

    # GraphQL persisted-query hash self-heal. When HEB rotates a hash,
    # the request fails with "PersistedQueryNotFound"; the client can
    # rediscover the new hash via Playwright and retry once. Overrides
    # are persisted across spawns so subsequent cold starts skip discovery.
    hash_overrides_path: Path | None = Field(
        default=None,
        description="JSON file storing rotated GraphQL hashes; defaults to "
        "<auth_state_path's parent>/hash_overrides.json.",
    )
    hash_self_heal_enabled: bool = Field(
        default=True,
        description="Enable in-process rediscovery + retry on stale persisted-query hashes.",
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

    # Throttling - SSR
    max_concurrent_ssr_searches: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum concurrent SSR product searches",
    )
    min_ssr_delay_ms: int = Field(
        default=200,
        ge=0,
        le=5000,
        description="Minimum delay between SSR requests in milliseconds",
    )
    ssr_jitter_ms: int = Field(
        default=200,
        ge=0,
        le=1000,
        description="Random jitter added to SSR delay (0 to N ms)",
    )

    # Throttling - GraphQL
    max_concurrent_graphql: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent GraphQL API calls",
    )
    min_graphql_delay_ms: int = Field(
        default=100,
        ge=0,
        le=5000,
        description="Minimum delay between GraphQL requests in milliseconds",
    )
    graphql_jitter_ms: int = Field(
        default=100,
        ge=0,
        le=1000,
        description="Random jitter added to GraphQL delay (0 to N ms)",
    )

    # Throttling - Global
    throttling_enabled: bool = Field(
        default=True,
        description="Enable/disable request throttling globally",
    )

    # Session Auto-Refresh
    auto_refresh_enabled: bool = Field(
        default=True,
        description="Enable automatic session refresh before tool execution",
    )
    auto_refresh_threshold_hours: float = Field(
        default=4.0,
        ge=0.5,
        le=24.0,
        description="Refresh session when less than this many hours remaining",
    )
    auto_refresh_on_startup: bool = Field(
        default=False,
        description=(
            "Check and refresh session on MCP server startup (disabled by default - "
            "login should be explicit)"
        ),
    )
    auto_refresh_headless: bool = Field(
        default=True,
        description=(
            "Run the automatic background session refresh in headless mode. "
            "Set False in environments with a virtual display (e.g. xvfb in a "
            "container): HEB's Incapsula anti-bot returns HTTP 401 to the headless "
            "browser, so a headless auto-refresh can never renew the reese84 token "
            "and the session silently dies. A headed browser under xvfb passes the "
            "anti-bot, keeping the session self-sustaining."
        ),
    )
    heb_browser_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        description=(
            "User-Agent for BOTH the Playwright refresh browser and the httpx API "
            "client. MUST match the browser the session was captured from: HEB's "
            "Incapsula binds the reese84 token to the browser UA/fingerprint and "
            "REFUSES to renew it for a mismatched UA (the token's renewTime freezes "
            "and the session silently dies). capture_session.py writes the real UA "
            "to <auth_dir>/browser_ua.txt, which overrides this default."
        ),
    )
    reese84_keepwarm_interval_s: int = Field(
        default=540,
        ge=0,
        le=3600,
        description=(
            "Seconds between BACKGROUND reese84 keep-warm refreshes (0 = disabled). "
            "HEB's reese84 anti-bot token renews ~every 11 min; refreshing it "
            "proactively in the background (default ~9 min) keeps the session warm "
            "while idle, instead of only refreshing lazily before a tool call — which "
            "adds latency and clusters refreshes into op bursts (more anti-bot heat). "
            "Independent of auto_refresh_enabled (the lazy ensure_session path)."
        ),
    )

    def model_post_init(self, __context: Any) -> None:
        """Ensure auth state path is expanded."""
        if "~" in str(self.auth_state_path):
            object.__setattr__(
                self, "auth_state_path", Path(str(self.auth_state_path)).expanduser()
            )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_browser_user_agent() -> str:
    """Resolve the User-Agent for the refresh browser + httpx API client.

    Prefers ``<auth_dir>/browser_ua.txt`` (written by capture_session.py from the
    real browser the session was captured in) so the UA always matches the
    captured fingerprint; falls back to ``settings.heb_browser_user_agent``.
    Read fresh on each call (not cached) so a re-capture takes effect without a
    process restart.

    HEB's Incapsula binds the reese84 anti-bot token to the browser UA: if the
    refresh/API UA doesn't match the UA the token was issued under, Incapsula
    won't renew it (renewTime freezes) and the session silently dies.
    """
    settings = get_settings()
    try:
        sidecar = Path(settings.auth_state_path).expanduser().parent / "browser_ua.txt"
        if sidecar.exists():
            ua = sidecar.read_text(encoding="utf-8").strip()
            if ua:
                return ua
    except OSError:
        pass
    return settings.heb_browser_user_agent
