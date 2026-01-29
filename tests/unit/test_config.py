"""Tests for configuration module."""

import os
from unittest.mock import patch


def test_settings_loads_defaults():
    """Settings should have sensible defaults."""
    from texas_grocery_mcp.utils.config import Settings

    settings = Settings()

    assert settings.log_level == "INFO"
    assert settings.environment == "development"


def test_settings_loads_from_env():
    """Settings should load from environment variables."""
    with patch.dict(os.environ, {"HEB_DEFAULT_STORE": "123", "LOG_LEVEL": "DEBUG"}):
        from importlib import reload

        import texas_grocery_mcp.utils.config as config_module

        reload(config_module)
        settings = config_module.Settings()

        assert settings.heb_default_store == "123"
        assert settings.log_level == "DEBUG"


def test_auth_state_path_expands_home():
    """Auth state path should expand ~ to home directory."""
    from texas_grocery_mcp.utils.config import Settings

    settings = Settings()

    assert "~" not in str(settings.auth_state_path)
    assert settings.auth_state_path.name == "auth.json"
