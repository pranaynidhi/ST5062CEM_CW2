#!/usr/bin/env python3
"""
Base notifier interface for HoneyGrid notification system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import IntEnum
import time
import logging


logger = logging.getLogger(__name__)


class Severity(IntEnum):
    """Event severity levels (ordered)."""
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5
    
    @classmethod
    def from_event_type(cls, event_type: str) -> 'Severity':
        """
        Determine severity from event type.
        
        Args:
            event_type: Event type string
        
        Returns:
            Severity level
        """
        severity_map = {
            'created': cls.LOW,
            'modified': cls.HIGH,
            'opened': cls.CRITICAL,
            'deleted': cls.HIGH,
            'moved': cls.MEDIUM
        }
        return severity_map.get(event_type.lower(), cls.MEDIUM)


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    enabled: bool = True
    rate_limit_seconds: int = 60  # Minimum seconds between notifications
    batch_mode: bool = False  # Send digest instead of individual alerts
    batch_interval_seconds: int = 3600  # Batch interval (1 hour default)
    min_severity: Severity = Severity.LOW  # Minimum severity to notify
    channels: List[str] = field(default_factory=lambda: ['email'])
    metadata: Dict[str, Any] = field(default_factory=dict)


class Notifier(ABC):
    """
    Abstract base class for notification channels.
    """
    
    def __init__(self, config: NotificationConfig):
        """
        Initialize notifier.
        
        Args:
            config: Notification configuration
        """
        self.config = config
        self.last_notification_time = 0
        self._last_notification_time = {}
        self.pending_events = []
        
    @abstractmethod
    async def send(self, event: Dict[str, Any]) -> bool:
        """
        Send a single event notification.
        
        Args:
            event: Event data dictionary
        
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    @abstractmethod
    async def send_batch(self, events: List[Dict[str, Any]]) -> bool:
        """
        Send multiple events as a batch/digest.
        
        Args:
            events: List of event dictionaries
        
        Returns:
            True if sent successfully, False otherwise
        """
        pass
    
    def _get_current_time(self) -> float:
        return time.time()

    def _get_rate_limit_key(self, event: Dict[str, Any]) -> str:
        return str(event.get('token_id', 'default'))

    def _normalize_severity(self, value: Any) -> Severity:
        if isinstance(value, Severity):
            return value
        if isinstance(value, int):
            try:
                return Severity(value)
            except ValueError:
                return Severity.MEDIUM
        if isinstance(value, str):
            lookup = {
                'info': Severity.INFO,
                'low': Severity.LOW,
                'medium': Severity.MEDIUM,
                'high': Severity.HIGH,
                'critical': Severity.CRITICAL
            }
            return lookup.get(value.lower(), Severity.MEDIUM)
        return Severity.MEDIUM

    def _should_notify(self, event: Dict[str, Any]) -> bool:
        """Internal notify check with severity + rate limit."""
        if not self.config.enabled:
            return False

        event_severity = event.get('severity')
        if event_severity is None:
            event_type = event.get('event_type', '')
            severity = Severity.from_event_type(event_type)
        else:
            severity = self._normalize_severity(event_severity)

        if severity < self.config.min_severity:
            return False

        if self.config.rate_limit_seconds > 0:
            key = self._get_rate_limit_key(event)
            current_time = self._get_current_time()
            last_time = self._last_notification_time.get(key, 0)
            if current_time - last_time < self.config.rate_limit_seconds:
                logger.debug(
                    "Rate limit not met: "
                    f"{current_time - last_time}s since last notification"
                )
                return False

        return True

    def should_notify(self, event: Dict[str, Any]) -> bool:
        """Public notify check (backwards compatible)."""
        return self._should_notify(event)
    
    async def notify(self, event: Dict[str, Any]) -> bool:
        """
        Notify about an event (handles batching if configured).
        
        Args:
            event: Event data
        
        Returns:
            True if notification sent/queued successfully
        """
        if not self._should_notify(event):
            return False
        
        if self.config.batch_mode:
            self.pending_events.append(event)
            logger.info(f"Event queued for batch notification ({len(self.pending_events)} pending)")
            return True
        else:
            success = await self.send(event)
            if success:
                current_time = self._get_current_time()
                key = self._get_rate_limit_key(event)
                self._last_notification_time[key] = current_time
                self.last_notification_time = current_time
            return success
    
    async def flush_batch(self) -> bool:
        """
        Send all pending events as a batch.
        
        Returns:
            True if batch sent successfully
        """
        if not self.pending_events:
            return True
        
        logger.info(f"Sending batch notification with {len(self.pending_events)} events")
        success = await self.send_batch(self.pending_events)
        
        if success:
            self.pending_events.clear()
            current_time = self._get_current_time()
            self._last_notification_time["batch"] = current_time
            self.last_notification_time = current_time
        
        return success
    
    def format_event_summary(self, event: Dict[str, Any]) -> str:
        """
        Format event as human-readable summary.
        
        Args:
            event: Event data
        
        Returns:
            Formatted summary string
        """
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        path = event.get('path', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        timestamp = event.get('timestamp', time.time())
        
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        severity = Severity.from_event_type(event_type)
        
        return (
            f"🚨 HONEYTOKEN TRIGGERED [{severity.value.upper()}]\n"
            f"Time: {time_str}\n"
            f"Agent: {agent_id}\n"
            f"Token: {token_id}\n"
            f"Action: {event_type.upper()}\n"
            f"Path: {path}"
        )
