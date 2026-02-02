#!/usr/bin/env python3
"""
Discord notifier for HoneyGrid events using webhooks.
"""

import aiohttp
import asyncio
from typing import Dict, Any, List, Optional
import logging
import time

from .base import Notifier, NotificationConfig, Severity

logger = logging.getLogger(__name__)

class DiscordNotifier(Notifier):
    """
    Discord notification channel using webhooks.
    """
    def __init__(
        self,
        config: NotificationConfig,
        webhook_url: str,
        username: str = "HoneyGrid Bot",
        avatar_url: Optional[str] = None
    ):
        """
        Initialize Discord notifier.
        
        Args:
            config: Notification configuration
            webhook_url: Discord webhook URL
            username: Bot display name
            avatar_url: Bot avatar URL (optional)
        """
        super().__init__(config)
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url
        if not self.webhook_url:
            logger.warning("No Discord webhook URL configured")

        self._severity_colors = {
            Severity.INFO: 0x3498db,
            Severity.LOW: 0x2ecc71,
            Severity.MEDIUM: 0xf39c12,
            Severity.HIGH: 0xe67e22,
            Severity.CRITICAL: 0xe74c3c
        }

    async def send(self, event: Dict[str, Any]) -> bool:
        """Send single event notification to Discord."""
        if not self.webhook_url:
            logger.error("No Discord webhook URL configured")
            return False
        try:
            payload = self._create_message(event)
            return await self._post_to_discord(payload)
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    async def send_batch(self, events: List[Dict[str, Any]]) -> bool:
        """Send batch digest to Discord."""
        if not self.webhook_url:
            logger.error("No Discord webhook URL configured")
            return False
        if not events:
            return True
        try:
            payload = self._create_batch_message(events)
            return await self._post_to_discord(payload)
        except Exception as e:
            logger.error(f"Failed to send Discord batch notification: {e}")
            return False

    async def _post_to_discord(self, payload: Dict[str, Any]) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status in (200, 204):
                        logger.info("Discord notification sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord webhook error {response.status}: {error_text}")
                        return False
        except asyncio.TimeoutError:
            logger.error("Discord webhook timeout")
            return False
        except Exception as e:
            logger.error(f"Discord webhook request failed: {e}")
            return False

    def _get_embed_color(self, severity: Severity) -> int:
        """Return embed color for severity."""
        return self._severity_colors.get(severity, 0x95a5a6)

    def _format_embed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Format Discord embed payload."""
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        path = event.get('path', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        timestamp = event.get('timestamp', time.time())
        severity = event.get('severity')
        if severity is None:
            severity = Severity.from_event_type(event_type)
        color = self._get_embed_color(severity)
        embed = {
            "title": f"HoneyGrid Alert - {severity.name}",
            "description": f"A honeytoken was triggered by agent **{agent_id}**.",
            "color": color,
            "fields": [
                {"name": "Agent", "value": agent_id, "inline": True},
                {"name": "Token", "value": token_id, "inline": True},
                {"name": "Event Type", "value": event_type, "inline": True},
                {"name": "Path", "value": f"`{path}`", "inline": False}
            ],
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(timestamp))
        }
        return embed

    def _create_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        embed = self._format_embed(event)
        payload = {
            "username": self.username,
            "embeds": [embed]
        }
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        return payload

    def _create_batch_message(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        severity_counts = {}
        for event in events:
            event_type = event.get('event_type', '')
            severity = Severity.from_event_type(event_type)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        summary_lines = []
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            count = severity_counts.get(severity, 0)
            if count > 0:
                summary_lines.append(f"{severity.value.upper()}: {count}")
        summary_text = "\n".join(summary_lines)
        event_lines = []
        for i, event in enumerate(events[:10], 1):
            agent_id = event.get('agent_id', 'Unknown')
            event_type = event.get('event_type', 'Unknown')
            token_id = event.get('token_id', 'Unknown')
            timestamp = event.get('timestamp', time.time())
            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
            event_lines.append(f"{i}. `{time_str}` - {agent_id} - {event_type.upper()} - {token_id}")
        if len(events) > 10:
            event_lines.append(f"... and {len(events) - 10} more events")
        events_text = "\n".join(event_lines)
        embed = {
            "title": f"HoneyGrid Alert Digest - {len(events)} Events",
            "description": f"Summary by Severity:\n{summary_text}\n\nRecent Events:\n{events_text}",
            "color": 0x2c3e50,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(time.time()))
        }
        payload = {
            "username": self.username,
            "embeds": [embed]
        }
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        return payload
