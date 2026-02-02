#!/usr/bin/env python3
"""
Unit Tests for Notification System
Tests EmailNotifier, DiscordNotifier, and Severity levels.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import Mock, patch, AsyncMock
from server.notifiers import (
    NotificationConfig,
    Severity,
    EmailNotifier,
    DiscordNotifier,
)


class TestSeverity:
    """Test Severity enum."""

    def test_severity_ordering(self):
        """Test that severity levels are ordered correctly."""
        assert Severity.INFO.value < Severity.LOW.value
        assert Severity.LOW.value < Severity.MEDIUM.value
        assert Severity.MEDIUM.value < Severity.HIGH.value
        assert Severity.HIGH.value < Severity.CRITICAL.value

    def test_severity_comparison(self):
        """Test severity level comparisons."""
        assert Severity.INFO < Severity.CRITICAL
        assert Severity.HIGH > Severity.LOW
        assert Severity.MEDIUM == Severity.MEDIUM


class TestNotificationConfig:
    """Test NotificationConfig."""

    def test_default_config(self):
        """Test creating config with defaults."""
        config = NotificationConfig()

        assert config.enabled is True
        assert config.rate_limit_seconds == 60
        assert config.batch_mode is False
        assert config.min_severity == Severity.LOW

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = NotificationConfig(
            enabled=False,
            rate_limit_seconds=120,
            batch_mode=True,
            min_severity=Severity.HIGH,
        )

        assert config.enabled is False
        assert config.rate_limit_seconds == 120
        assert config.batch_mode is True
        assert config.min_severity == Severity.HIGH


class TestEmailNotifier:
    """Test EmailNotifier."""

    def test_init(self):
        """Test EmailNotifier initialization."""
        config = NotificationConfig()
        notifier = EmailNotifier(
            config=config,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="password",
            from_address="honeygrid@example.com",
            to_addresses=["admin@example.com"],
        )

        assert notifier.smtp_host == "smtp.example.com"
        assert notifier.smtp_port == 587
        assert notifier.from_address == "honeygrid@example.com"
        assert len(notifier.to_addresses) == 1

    def test_should_notify_severity_filter(self):
        """Test that notifications are filtered by severity."""
        config = NotificationConfig(min_severity=Severity.HIGH)
        notifier = EmailNotifier(
            config=config,
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
        )

        # Should not notify for LOW severity
        event = {"severity": Severity.LOW}
        assert not notifier._should_notify(event)

        # Should notify for HIGH severity
        event = {"severity": Severity.HIGH}
        assert notifier._should_notify(event)

        # Should notify for CRITICAL severity
        event = {"severity": Severity.CRITICAL}
        assert notifier._should_notify(event)

    def test_format_subject(self):
        """Test email subject formatting."""
        config = NotificationConfig()
        notifier = EmailNotifier(
            config=config,
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
        )

        event = {
            "agent_id": "agent-001",
            "token_id": "token-123",
            "event_type": "opened",
        }

        subject = notifier._format_subject(event)

        assert "agent-001" in subject
        assert "token-123" in subject or "opened" in subject

    def test_format_body(self):
        """Test email body formatting."""
        config = NotificationConfig()
        notifier = EmailNotifier(
            config=config,
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
        )

        event = {
            "agent_id": "agent-001",
            "token_id": "token-123",
            "event_type": "opened",
            "path": "/tmp/secret.txt",
            "timestamp": 1234567890,
        }

        body = notifier._format_body(event)

        assert "agent-001" in body
        assert "token-123" in body
        assert "opened" in body
        assert "/tmp/secret.txt" in body


class TestDiscordNotifier:
    """Test DiscordNotifier."""

    def test_init(self):
        """Test DiscordNotifier initialization."""
        config = NotificationConfig()
        notifier = DiscordNotifier(
            config=config,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            username="HoneyGrid Bot",
        )

        assert notifier.webhook_url == "https://discord.com/api/webhooks/123/abc"
        assert notifier.username == "HoneyGrid Bot"

    def test_get_embed_color(self):
        """Test Discord embed color selection based on severity."""
        config = NotificationConfig()
        notifier = DiscordNotifier(
            config=config, webhook_url="https://discord.com/api/webhooks/123/abc"
        )

        # Test different severity levels
        assert notifier._get_embed_color(Severity.INFO) == 0x3498DB  # Blue
        assert notifier._get_embed_color(Severity.LOW) == 0x2ECC71  # Green
        assert notifier._get_embed_color(Severity.MEDIUM) == 0xF39C12  # Orange
        assert notifier._get_embed_color(Severity.HIGH) == 0xE67E22  # Dark orange
        assert notifier._get_embed_color(Severity.CRITICAL) == 0xE74C3C  # Red

    def test_format_embed(self):
        """Test Discord embed formatting."""
        config = NotificationConfig()
        notifier = DiscordNotifier(
            config=config, webhook_url="https://discord.com/api/webhooks/123/abc"
        )

        event = {
            "agent_id": "agent-001",
            "token_id": "token-123",
            "event_type": "opened",
            "path": "/tmp/secret.txt",
            "timestamp": 1234567890,
            "severity": Severity.HIGH,
        }

        embed = notifier._format_embed(event)

        assert "title" in embed
        assert "description" in embed
        assert "color" in embed
        assert "fields" in embed

        # Check that key info is in fields (field names have emoji prefixes)
        fields = {f["name"]: f["value"] for f in embed["fields"]}
        # Fields have emoji prefixes like "🧭 Agent", "🔖 Token", etc.
        field_names = set(fields.keys())
        assert any("Agent" in name for name in field_names), f"Agent field not found in {field_names}"
        assert any("Token" in name for name in field_names), f"Token field not found in {field_names}"
        assert any("Event" in name for name in field_names), f"Event field not found in {field_names}"

    @pytest.mark.asyncio
    async def test_notify_disabled(self):
        """Test that notification is skipped when disabled."""
        config = NotificationConfig(enabled=False)
        notifier = DiscordNotifier(
            config=config, webhook_url="https://discord.com/api/webhooks/123/abc"
        )

        event = {"agent_id": "test", "severity": Severity.HIGH}

        # Should not raise error and should skip
        await notifier.notify(event)


class TestRateLimiting:
    """Test rate limiting functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_blocks_duplicate(self):
        """Test that rate limiting prevents duplicate notifications."""
        config = NotificationConfig(rate_limit_seconds=60)
        notifier = EmailNotifier(
            config=config,
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="from@example.com",
            to_addresses=["to@example.com"],
        )

        event = {
            "agent_id": "agent-001",
            "token_id": "token-123",
            "severity": Severity.HIGH,
        }

        # First notification should pass
        assert notifier._should_notify(event)

        # Record the notification
        key = notifier._get_rate_limit_key(event)
        notifier._last_notification_time[key] = notifier._get_current_time()

        # Second notification within rate limit should be blocked
        assert not notifier._should_notify(event)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
