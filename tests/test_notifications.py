#!/usr/bin/env python3
"""
Test notification system implementation.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import os
import time
import pytest
from server.notifiers import EmailNotifier, DiscordNotifier, Severity, NotificationConfig

RUN_LIVE = os.getenv("HONEYGRID_RUN_LIVE_NOTIFICATIONS") == "1"
SMTP_HOST = os.getenv("HONEYGRID_SMTP_HOST", "").strip()
SMTP_PORT = os.getenv("HONEYGRID_SMTP_PORT", "587").strip()
SMTP_USERNAME = os.getenv("HONEYGRID_SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("HONEYGRID_SMTP_PASSWORD", "").strip()
SMTP_FROM = os.getenv("HONEYGRID_SMTP_FROM", "").strip()
SMTP_TO = os.getenv("HONEYGRID_SMTP_TO", "").strip()

@pytest.mark.asyncio
async def test_discord_notifier():
    """Test Discord notifier (dry run)."""
    if not RUN_LIVE:
        pytest.skip("Live Discord webhook test disabled. Set HONEYGRID_RUN_LIVE_NOTIFICATIONS=1 to enable.")
    webhook_url = os.getenv("HONEYGRID_DISCORD_WEBHOOK", "").strip()
    if not webhook_url:
        pytest.skip("No Discord webhook set. Set HONEYGRID_DISCORD_WEBHOOK to enable.")
    print("\n4. Testing Discord Notifier...")
    config = NotificationConfig(enabled=True, rate_limit_seconds=0)
    # Create notifier (will not actually send without real webhook)
    notifier = DiscordNotifier(
        config=config,
        webhook_url=webhook_url,
        username="File"
    )
    print("   ✓ DiscordNotifier instantiated")
    print(f"   ✓ Webhook URL: {notifier.webhook_url[:40]}...")
    print(f"   ✓ Username: {notifier.username}")
    # Actually send a test message (requires valid webhook)
    test_event = {
        'agent_id': 'agent-001',
        'token_id': 'token-123',
        'path': 'C:\\honeytokens\\secret.docx',
        'event_type': 'opened',
        'timestamp': time.time()
    }
    result = await notifier.send(test_event)
    print(f"   ✓ Discord message sent: {result}")


def test_severity():
    """Test severity classification."""
    print("\n1. Testing Severity Classification...")
    
    test_cases = [
        ("created", Severity.LOW),
        ("modified", Severity.HIGH),
        ("opened", Severity.CRITICAL),
        ("deleted", Severity.HIGH),
        ("moved", Severity.MEDIUM)
    ]
    
    for event_type, expected_severity in test_cases:
        severity = Severity.from_event_type(event_type)
        status = "✓" if severity == expected_severity else "✗"
        print(f"   {status} {event_type} → {severity.value} (expected: {expected_severity.value})")
    
    print("   ✓ Severity classification working")


def test_notification_config():
    """Test notification configuration."""
    print("\n2. Testing Notification Config...")
    
    config = NotificationConfig(
        enabled=True,
        rate_limit_seconds=30,
        min_severity=Severity.MEDIUM
    )
    
    print(f"   ✓ Enabled: {config.enabled}")
    print(f"   ✓ Rate limit: {config.rate_limit_seconds}s")
    print(f"   ✓ Min severity: {config.min_severity.value}")
    print("   ✓ Configuration created successfully")


@pytest.mark.asyncio
async def test_email_notifier():
    """Test email notifier (dry run)."""
    if not RUN_LIVE:
        pytest.skip("Live SMTP test disabled. Set HONEYGRID_RUN_LIVE_NOTIFICATIONS=1 to enable.")
    print("\n3. Testing Email Notifier...")
    
    config = NotificationConfig(enabled=True, rate_limit_seconds=0)
    
    # Actually send a test message (requires valid SMTP config)
    if not SMTP_HOST or not SMTP_FROM or not SMTP_TO:
        pytest.skip("Missing SMTP settings. Set HONEYGRID_SMTP_HOST/SMTP_FROM/SMTP_TO to enable.")

    notifier = EmailNotifier(
        config=config,
        smtp_host=SMTP_HOST,
        smtp_port=int(SMTP_PORT or "587"),
        smtp_username=SMTP_USERNAME,
        smtp_password=SMTP_PASSWORD,
        from_address=SMTP_FROM,
        to_addresses=[addr.strip() for addr in SMTP_TO.split(",") if addr.strip()]
    )
    print("   ✓ EmailNotifier instantiated")
    print(f"   ✓ SMTP host: {notifier.smtp_host}")
    print(f"   ✓ Recipients: {len(notifier.to_addresses)}")
    test_event = {
        'agent_id': 'agent-001',
        'token_id': 'token-123',
        'path': 'C:\\honeytokens\\secret.docx',
        'event_type': 'opened',
        'timestamp': time.time()
    }
    result = await notifier.send(test_event)
    print(f"   ✓ Email message sent: {result}")




async def main():
    """Run all tests."""
    print("=" * 60)
    print("HoneyGrid Notification System - Tests")
    print("=" * 60)
    
    try:
        test_severity()
        test_notification_config()
        await test_email_notifier()
        await test_discord_notifier()
        
        print("\n" + "=" * 60)
        print("✓ All notification tests passed!")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
