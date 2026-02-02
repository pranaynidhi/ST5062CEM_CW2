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

    def _get_severity_emoji(self, severity: Severity) -> str:
        """Return emoji for severity."""
        emoji_map = {
            Severity.INFO: "ℹ️",
            Severity.LOW: "🟢",
            Severity.MEDIUM: "🟡",
            Severity.HIGH: "🟠",
            Severity.CRITICAL: "🔴"
        }
        return emoji_map.get(severity, "⚪")

    def _safe_code_block(self, value: str, max_len: int = 1000) -> str:
        """Format a value in a code block with length guard."""
        if value is None:
            value = ""
        if len(value) > max_len:
            value = value[: max_len - 3] + "..."
        return f"`{value}`"

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
        severity_emoji = self._get_severity_emoji(severity)
        event_type_label = event_type.upper()
        embed = {
            "title": f"{severity_emoji} HoneyGrid Alert • {severity.name}",
            "description": f"A honeytoken was triggered by agent **{agent_id}**.",
            "color": color,
            "author": {
                "name": "HoneyGrid Security Monitor",
            },
            "fields": [
                {"name": "🧭 Agent", "value": self._safe_code_block(agent_id), "inline": True},
                {"name": "🔖 Token", "value": self._safe_code_block(token_id), "inline": True},
                {"name": "⚡ Event", "value": self._safe_code_block(event_type_label), "inline": True},
                {"name": "🗂️ Path", "value": self._safe_code_block(path), "inline": False},
            ],
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(timestamp)),
            "footer": {
                "text": "HoneyGrid • Distributed Honeytoken Monitor"
            }
        }
        if self.avatar_url:
            embed["author"]["icon_url"] = self.avatar_url
            embed["thumbnail"] = {"url": self.avatar_url}
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

        summary_fields = []
        for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            count = severity_counts.get(severity, 0)
            if count > 0:
                emoji = self._get_severity_emoji(severity)
                summary_fields.append({
                    "name": f"{emoji} {severity.name}",
                    "value": self._safe_code_block(str(count)),
                    "inline": True
                })

        event_lines = []
        for i, event in enumerate(events[:10], 1):
            agent_id = event.get('agent_id', 'Unknown')
            event_type = event.get('event_type', 'Unknown')
            token_id = event.get('token_id', 'Unknown')
            timestamp = event.get('timestamp', time.time())
            time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
            event_lines.append(f"{i}. `{time_str}` • {agent_id} • {event_type.upper()} • {token_id}")
        if len(events) > 10:
            event_lines.append(f"... and {len(events) - 10} more events")
        events_text = "\n".join(event_lines)

        embed = {
            "title": f"📌 HoneyGrid Digest • {len(events)} Events",
            "description": "Summary by Severity and recent activity.",
            "color": 0x2c3e50,
            "fields": summary_fields + [
                {
                    "name": "🧾 Recent Events",
                    "value": events_text or "No recent events",
                    "inline": False
                }
            ],
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime(time.time())),
            "footer": {
                "text": "HoneyGrid • Digest"
            }
        }
        if self.avatar_url:
            embed["thumbnail"] = {"url": self.avatar_url}

        payload = {
            "username": self.username,
            "embeds": [embed]
        }
        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url
        return payload
