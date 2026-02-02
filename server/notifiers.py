#!/usr/bin/env python3
"""
HoneyGrid Notification System
Supports email and Discord notifications for honeytoken triggers.
"""

import asyncio
import aiosmtplib
import smtplib
import aiohttp
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import IntEnum
from functools import total_ordering


logger = logging.getLogger(__name__)


@total_ordering
class Severity(IntEnum):
    """Severity levels for notifications (with natural ordering)."""
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5
    
    def __lt__(self, other):
        if not isinstance(other, Severity):
            return NotImplemented
        return self.value < other.value


@dataclass
class NotificationConfig:
    """Configuration for notification channels."""
    enabled: bool = True
    rate_limit_seconds: int = 60
    batch_mode: bool = False
    batch_interval_seconds: int = 3600
    min_severity: Severity = Severity.LOW


class BaseNotifier:
    """Base class for notification channels."""
    
    def __init__(self, config: NotificationConfig):
        """
        Initialize base notifier.
        
        Args:
            config: Notification configuration
        """
        self.config = config
        self._last_notification_time = {}
    
    def _should_notify(self, event: Dict[str, Any]) -> bool:
        """
        Check if notification should be sent based on config.
        
        Args:
            event: Event data
        
        Returns:
            True if notification should be sent
        """
        if not self.config.enabled:
            return False
        
        # Check severity level
        event_severity = event.get('severity', Severity.LOW)
        if isinstance(event_severity, int):
            event_severity = Severity(event_severity)
        
        if event_severity < self.config.min_severity:
            return False
        
        # Rate limiting
        if self.config.rate_limit_seconds > 0:
            event_key = event.get('token_id', 'default')
            last_time = self._last_notification_time.get(event_key, 0)
            current_time = time.time()
            
            if current_time - last_time < self.config.rate_limit_seconds:
                return False
            
            self._last_notification_time[event_key] = current_time
        
        return True
    
    def should_notify(self, event: Dict[str, Any]) -> bool:
        """Public alias for _should_notify for backwards compatibility."""
        return self._should_notify(event)
    
    async def notify(self, event: Dict[str, Any]) -> bool:
        """
        Send notification (to be implemented by subclasses).
        
        Args:
            event: Event data
        
        Returns:
            True if notification was sent successfully
        """
        raise NotImplementedError


class EmailNotifier(BaseNotifier):
    """Email notification channel."""
    
    def __init__(
        self,
        config: NotificationConfig,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_username: str = '',
        smtp_password: str = '',
        from_address: str = 'honeygrid@example.com',
        to_addresses: List[str] = None,
        use_tls: bool = True
    ):
        """
        Initialize email notifier.
        
        Args:
            config: Notification configuration
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP authentication username
            smtp_password: SMTP authentication password
            from_address: Sender email address
            to_addresses: List of recipient email addresses
            use_tls: Use TLS for SMTP connection
        """
        super().__init__(config)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.to_addresses = to_addresses or []
        self.use_tls = use_tls
    
    def _format_subject(self, event: Dict[str, Any]) -> str:
        """Format email subject line."""
        severity = event.get('severity', Severity.LOW)
        agent_id = event.get('agent_id', 'Unknown')
        event_type = event.get('event_type', 'access')
        token_id = event.get('token_id', 'Unknown')
        
        return f"[HoneyGrid] {severity.name} Alert: Honeytoken {event_type} by {agent_id} (token: {token_id})"
    
    def _format_body(self, event: Dict[str, Any]) -> str:
        """Format email body."""
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        path = event.get('path', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        severity = event.get('severity', Severity.LOW)
        timestamp = event.get('timestamp', 0)
        
        body = f"""
HoneyGrid Alert

Severity: {severity.name}
Agent: {agent_id}
Token: {token_id}
Path: {path}
Event Type: {event_type}
Timestamp: {timestamp}

A honeytoken has been triggered. Please investigate immediately.

-- 
HoneyGrid Monitoring System
"""
        return body
    
    async def notify(self, event: Dict[str, Any]) -> bool:
        """
        Send email notification.
        
        Args:
            event: Event data
        
        Returns:
            True if email was sent successfully
        """
        if not self._should_notify(event):
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_address
            msg['To'] = ', '.join(self.to_addresses)
            msg['Subject'] = self._format_subject(event)
            
            body = self._format_body(event)
            msg.attach(MIMEText(body, 'plain'))
            
            # Send via async SMTP
            if self.use_tls:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_username,
                    password=self.smtp_password,
                    use_tls=True
                )
            else:
                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_username,
                    password=self.smtp_password,
                    use_tls=False
                )
            
            logger.info(f"Email notification sent to {len(self.to_addresses)} recipients")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False


class DiscordNotifier(BaseNotifier):
    """Discord webhook notification channel."""
    
    # Embed colors for different severities
    SEVERITY_COLORS = {
        Severity.INFO: 0x3498db,      # Blue
        Severity.LOW: 0x2ecc71,       # Green
        Severity.MEDIUM: 0xf39c12,    # Orange
        Severity.HIGH: 0xe67e22,      # Dark orange
        Severity.CRITICAL: 0xe74c3c,  # Red
    }
    
    def __init__(
        self,
        config: NotificationConfig,
        webhook_url: str,
        username: str = 'HoneyGrid Bot',
        avatar_url: Optional[str] = None
    ):
        """
        Initialize Discord notifier.
        
        Args:
            config: Notification configuration
            webhook_url: Discord webhook URL
            username: Bot username to display
            avatar_url: Bot avatar URL (optional)
        """
        super().__init__(config)
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url
    
    def _get_embed_color(self, severity: Severity) -> int:
        """Get embed color for severity level."""
        return self.SEVERITY_COLORS.get(severity, 0x95a5a6)
    
    def _format_embed(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Format Discord embed."""
        severity = event.get('severity', Severity.LOW)
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        path = event.get('path', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        timestamp = event.get('timestamp', 0)
        
        embed = {
            'title': f'🚨 Honeytoken Triggered: {event_type.upper()}',
            'description': f'A honeytoken has been accessed on **{agent_id}**',
            'color': self._get_embed_color(severity),
            'fields': [
                {
                    'name': '⚠️ Severity',
                    'value': severity.name,
                    'inline': True
                },
                {
                    'name': 'Agent',
                    'value': agent_id,
                    'inline': True
                },
                {
                    'name': 'Token',
                    'value': token_id,
                    'inline': True
                },
                {
                    'name': 'Path',
                    'value': f'`{path}`',
                    'inline': False
                },
                {
                    'name': 'Event Type',
                    'value': event_type,
                    'inline': True
                }
            ],
            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(timestamp)),
            'footer': {
                'text': 'HoneyGrid Monitoring System'
            }
        }
        
        return embed
    
    async def notify(self, event: Dict[str, Any]) -> bool:
        """
        Send Discord notification.
        
        Args:
            event: Event data
        
        Returns:
            True if notification was sent successfully
        """
        if not self._should_notify(event):
            return False
        
        try:
            embed = self._format_embed(event)
            
            payload = {
                'username': self.username,
                'embeds': [embed]
            }
            
            if self.avatar_url:
                payload['avatar_url'] = self.avatar_url
            
            # Send via webhook
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        logger.info("Discord notification sent successfully")
                        return True
                    else:
                        logger.warning(f"Discord webhook returned status {response.status}")
                        return False
        
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False


# Example usage
if __name__ == '__main__':
    import asyncio
    
    # Create config
    config = NotificationConfig(
        enabled=True,
        rate_limit_seconds=60,
        min_severity=Severity.MEDIUM
    )
    
    # Test event
    event = {
        'agent_id': 'agent-001',
        'token_id': 'token-abc123',
        'path': 'C:\\honeytokens\\secret.docx',
        'event_type': 'opened',
        'severity': Severity.HIGH,
        'timestamp': int(time.time())
    }
    
    print("Notification System Test")
    print("=" * 60)
    print(f"\nEvent: {event}")
    print(f"\nSeverity ordering test:")
    print(f"  INFO < LOW: {Severity.INFO < Severity.LOW}")
    print(f"  MEDIUM < HIGH: {Severity.MEDIUM < Severity.HIGH}")
    print(f"  HIGH > LOW: {Severity.HIGH > Severity.LOW}")
