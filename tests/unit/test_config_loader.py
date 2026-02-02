#!/usr/bin/env python3
"""
Unit Tests for Configuration Loader
Tests YAML loading, environment overrides, and config merging.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tempfile
import os
import yaml
from server.config_loader import (
    load_config,
    apply_env_overrides,
    merge_configs,
    get_nested_value,
    DEFAULT_SERVER_CONFIG,
)


class TestConfigLoader:
    """Test configuration loading functionality."""

    def test_load_default_config(self):
        """Test that default config is valid."""
        assert DEFAULT_SERVER_CONFIG is not None
        assert "server" in DEFAULT_SERVER_CONFIG
        assert "notifications" in DEFAULT_SERVER_CONFIG
        assert DEFAULT_SERVER_CONFIG["server"]["port"] == 9000

    def test_load_config_from_yaml(self):
        """Test loading config from YAML file."""
        # Create temporary YAML config
        config_data = {
            "server": {"host": "127.0.0.1", "port": 8000},
            "notifications": {"enabled": True, "min_severity": "high"},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            # Save and clear environment variables that might override values
            old_host = os.environ.pop("HONEYGRID_SERVER_HOST", None)
            old_port = os.environ.pop("HONEYGRID_SERVER_PORT", None)
            try:
                config = load_config(temp_path)
                assert config["server"]["host"] == "127.0.0.1"
                assert config["server"]["port"] == 8000
                assert config["notifications"]["enabled"] is True
            finally:
                # Restore environment variables
                if old_host is not None:
                    os.environ["HONEYGRID_SERVER_HOST"] = old_host
                if old_port is not None:
                    os.environ["HONEYGRID_SERVER_PORT"] = old_port
        finally:
            os.unlink(temp_path)

    def test_load_config_file_not_found(self):
        """Test loading config when file doesn't exist returns empty dict."""
        config = load_config("nonexistent.yaml")
        assert config == {}

        # With defaults, should return defaults
        config = load_config("nonexistent.yaml", defaults=DEFAULT_SERVER_CONFIG)
        assert config == DEFAULT_SERVER_CONFIG

    def test_merge_configs(self):
        """Test merging two configuration dictionaries."""
        base = {
            "server": {"port": 9000, "host": "0.0.0.0"},
            "database": {"path": "data.db"},
        }
        override = {"server": {"port": 8000}, "notifications": {"enabled": True}}

        merged = merge_configs(base, override)

        assert merged["server"]["port"] == 8000  # Overridden
        assert merged["server"]["host"] == "0.0.0.0"  # Preserved
        assert merged["database"]["path"] == "data.db"  # Preserved
        assert merged["notifications"]["enabled"] is True  # Added

    def test_apply_env_overrides(self):
        """Test applying environment variable overrides."""
        config = {
            "server": {"port": 9000, "host": "0.0.0.0"},
            "notifications": {"enabled": False},
        }

        # Set environment variables
        os.environ["HONEYGRID_SERVER_PORT"] = "8080"
        os.environ["HONEYGRID_NOTIFICATIONS_ENABLED"] = "true"

        try:
            result = apply_env_overrides(config)

            assert result["server"]["port"] == 8080
            assert result["notifications"]["enabled"] is True
        finally:
            # Cleanup
            os.environ.pop("HONEYGRID_SERVER_PORT", None)
            os.environ.pop("HONEYGRID_NOTIFICATIONS_ENABLED", None)

    def test_get_nested_value(self):
        """Test getting nested values from config dict."""
        config = {"server": {"database": {"path": "data.db"}}}

        value = get_nested_value(config, "server.database.path")
        assert value == "data.db"

        # Test default value
        value = get_nested_value(config, "nonexistent.key", "default")
        assert value == "default"

    def test_env_override_type_conversion(self):
        """Test that environment variables are converted to correct types."""
        config = {
            "server": {"port": 9000},
            "notifications": {"enabled": False},
            "timeout": 60.5,
        }

        os.environ["HONEYGRID_SERVER_PORT"] = "8080"
        os.environ["HONEYGRID_NOTIFICATIONS_ENABLED"] = "true"
        os.environ["HONEYGRID_TIMEOUT"] = "120.5"

        try:
            result = apply_env_overrides(config)

            assert isinstance(result["server"]["port"], int)
            assert result["server"]["port"] == 8080
            assert isinstance(result["notifications"]["enabled"], bool)
            assert result["notifications"]["enabled"] is True
            assert isinstance(result["timeout"], float)
            assert result["timeout"] == 120.5
        finally:
            os.environ.pop("HONEYGRID_SERVER_PORT", None)
            os.environ.pop("HONEYGRID_NOTIFICATIONS_ENABLED", None)
            os.environ.pop("HONEYGRID_TIMEOUT", None)


class TestNotificationConfig:
    """Test notification configuration structure."""

    def test_notification_config_in_default(self):
        """Test that notification config exists in defaults."""
        assert "notifications" in DEFAULT_SERVER_CONFIG
        notif = DEFAULT_SERVER_CONFIG["notifications"]

        assert "enabled" in notif
        assert "min_severity" in notif
        assert "rate_limit_seconds" in notif
        assert "batch_mode" in notif

    def test_email_config_structure(self):
        """Test email notification config structure."""
        notif = DEFAULT_SERVER_CONFIG["notifications"]

        assert "email" in notif
        email = notif["email"]

        assert "enabled" in email
        assert "smtp_host" in email
        assert "smtp_port" in email
        assert "from_address" in email
        assert "to_addresses" in email

    def test_discord_config_structure(self):
        """Test Discord notification config structure."""
        notif = DEFAULT_SERVER_CONFIG["notifications"]

        assert "discord" in notif
        discord = notif["discord"]

        assert "enabled" in discord
        assert "webhook_url" in discord
        assert "username" in discord


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
