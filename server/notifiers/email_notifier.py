#!/usr/bin/env python3
"""
Email notifier for HoneyGrid events.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
import logging
import time

from .base import Notifier, NotificationConfig, Severity


logger = logging.getLogger(__name__)


class EmailNotifier(Notifier):
    """
    Email notification channel using SMTP.
    """
    
    def __init__(
        self,
        config: NotificationConfig,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_username: str = "",
        smtp_password: str = "",
        from_address: str = "honeygrid@example.com",
        to_addresses: List[str] = None,
        use_tls: bool = True,
        logo_url: Optional[str] = None
    ):
        """
        Initialize email notifier.
        
        Args:
            config: Notification configuration
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            from_address: Sender email address
            to_addresses: List of recipient email addresses
            use_tls: Use TLS encryption
        """
        super().__init__(config)
        
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_address = from_address
        self.to_addresses = to_addresses or []
        self.use_tls = use_tls
        self.logo_url = logo_url
        
        if not self.to_addresses:
            logger.warning("No email recipients configured")
    
    async def send(self, event: Dict[str, Any]) -> bool:
        """Send single event notification email."""
        if not self.to_addresses:
            logger.error("No email recipients configured")
            return False
        
        try:
            subject = self._format_subject(event)
            body_text = self._format_body(event)
            body_html = self._create_html_body(event)
            
            return self._send_email(subject, body_text, body_html)
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False
    
    async def send_batch(self, events: List[Dict[str, Any]]) -> bool:
        """Send batch digest email."""
        if not self.to_addresses:
            logger.error("No email recipients configured")
            return False
        
        if not events:
            return True
        
        try:
            subject = f"HoneyGrid Alert Digest - {len(events)} events"
            body_text = self._create_batch_text_body(events)
            body_html = self._create_batch_html_body(events)
            
            return self._send_email(subject, body_text, body_html)
        
        except Exception as e:
            logger.error(f"Failed to send batch email: {e}")
            return False
    
    def _send_email(self, subject: str, text_body: str, html_body: str) -> bool:
        """
        Send email via SMTP.
        
        Args:
            subject: Email subject
            text_body: Plain text body
            html_body: HTML body
        
        Returns:
            True if sent successfully
        """
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.from_address
            message["To"] = ", ".join(self.to_addresses)
            
            # Attach both plain text and HTML parts
            part1 = MIMEText(text_body, "plain")
            part2 = MIMEText(html_body, "html")
            message.attach(part1)
            message.attach(part2)
            
            # Create SMTP connection
            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls(context=context)
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_address, self.to_addresses, message.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_address, self.to_addresses, message.as_string())
            
            logger.info(f"Email sent successfully to {len(self.to_addresses)} recipients")
            return True
        
        except Exception as e:
            logger.error(f"SMTP error: {e}")
            return False
    
    def _format_subject(self, event: Dict[str, Any]) -> str:
        """Format email subject line for tests and notifications."""
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        severity = event.get('severity')
        if severity is None:
            severity = Severity.from_event_type(event_type)
        return f"[HoneyGrid] {severity.name} Alert: {event_type} by {agent_id} (token: {token_id})"

    def _create_subject(self, event: Dict[str, Any]) -> str:
        """Backwards-compatible subject builder."""
        return self._format_subject(event)
    
    def _format_body(self, event: Dict[str, Any]) -> str:
        """Format plain text email body for tests and notifications."""
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        path = event.get('path', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        timestamp = event.get('timestamp', time.time())
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

        return (
            f"HoneyGrid Alert\n"
            f"Time: {time_str}\n"
            f"Agent: {agent_id}\n"
            f"Token: {token_id}\n"
            f"Event Type: {event_type}\n"
            f"Path: {path}\n"
        )

    def _create_text_body(self, event: Dict[str, Any]) -> str:
        """Backwards-compatible plain text body."""
        return self._format_body(event)
    
    def _create_html_body(self, event: Dict[str, Any]) -> str:
        """Create HTML email body."""
        agent_id = event.get('agent_id', 'Unknown')
        token_id = event.get('token_id', 'Unknown')
        path = event.get('path', 'Unknown')
        event_type = event.get('event_type', 'Unknown')
        timestamp = event.get('timestamp', time.time())
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        
        severity = Severity.from_event_type(event_type)
        severity_colors = {
            Severity.INFO: "#17a2b8",
            Severity.LOW: "#ffc107",
            Severity.MEDIUM: "#ff9800",
            Severity.HIGH: "#f44336",
            Severity.CRITICAL: "#d32f2f"
        }
        color = severity_colors.get(severity, "#f44336")
        logo_html = ""
        if self.logo_url:
            logo_html = (
                f"<div style=\"text-align:center; margin: 10px 0 15px;\">"
                f"<img src=\"{self.logo_url}\" alt=\"HoneyGrid\" "
                f"style=\"width:72px; height:72px; border-radius: 12px;\" />"
                f"</div>"
            )
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: {color}; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; }}
        .info-row {{ margin: 10px 0; padding: 10px; background: white; border-left: 3px solid {color}; }}
        .label {{ font-weight: bold; display: inline-block; width: 120px; }}
        .footer {{ margin-top: 20px; padding: 15px; background: #f1f1f1; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 HoneyGrid Alert</h2>
            <p style="margin: 0; font-size: 14px;">Severity: {severity.name}</p>
        </div>
        <div class="content">
            {logo_html}
            <div class="info-row">
                <span class="label">Time:</span>
                <span>{time_str}</span>
            </div>
            <div class="info-row">
                <span class="label">Agent:</span>
                <span>{agent_id}</span>
            </div>
            <div class="info-row">
                <span class="label">Token:</span>
                <span>{token_id}</span>
            </div>
            <div class="info-row">
                <span class="label">Action:</span>
                <span>{event_type.upper()}</span>
            </div>
            <div class="info-row">
                <span class="label">Path:</span>
                <span style="word-break: break-all;">{path}</span>
            </div>
        </div>
        <div class="footer">
            <p>This is an automated alert from HoneyGrid distributed honeytoken monitoring system.</p>
            <p style="margin: 0;">Do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _create_batch_text_body(self, events: List[Dict[str, Any]]) -> str:
        """Create plain text batch digest body."""
        header = f"HoneyGrid Alert Digest\n{'=' * 50}\n\n"
        header += f"Total events: {len(events)}\n"
        
        # Count by severity
        severity_counts = {}
        for event in events:
            event_type = event.get('event_type', '')
            severity = Severity.from_event_type(event_type)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        header += "\nEvents by severity:\n"
        for severity in Severity:
            count = severity_counts.get(severity, 0)
            if count > 0:
                header += f"  {severity.name}: {count}\n"
        
        header += "\n" + "=" * 50 + "\n\n"
        
        # List events
        events_text = ""
        for i, event in enumerate(events, 1):
            events_text += f"Event {i}:\n"
            events_text += self.format_event_summary(event)
            events_text += "\n\n"
        
        footer = (
            "---\n"
            "This is an automated digest from HoneyGrid.\n"
            "Do not reply to this email.\n"
        )
        
        return header + events_text + footer
    
    def _create_batch_html_body(self, events: List[Dict[str, Any]]) -> str:
        """Create HTML batch digest body."""
        # Count by severity
        severity_counts = {}
        for event in events:
            event_type = event.get('event_type', '')
            severity = Severity.from_event_type(event_type)
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        # Build severity summary
        severity_summary = ""
        for severity in Severity:
            count = severity_counts.get(severity, 0)
            if count > 0:
                severity_summary += f"<li>{severity.name}: {count}</li>"

        logo_html = ""
        if self.logo_url:
            logo_html = (
                f"<div style=\"text-align:center; margin: 10px 0 15px;\">"
                f"<img src=\"{self.logo_url}\" alt=\"HoneyGrid\" "
                f"style=\"width:72px; height:72px; border-radius: 12px;\" />"
                f"</div>"
            )
        
        # Build event list
        events_html = ""
        for i, event in enumerate(events, 1):
            agent_id = event.get('agent_id', 'Unknown')
            token_id = event.get('token_id', 'Unknown')
            path = event.get('path', 'Unknown')
            event_type = event.get('event_type', 'Unknown')
            timestamp = event.get('timestamp', time.time())
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            
            severity = Severity.from_event_type(event_type)
            severity_colors = {
                Severity.INFO: "#17a2b8",
                Severity.LOW: "#ffc107",
                Severity.MEDIUM: "#ff9800",
                Severity.HIGH: "#f44336",
                Severity.CRITICAL: "#d32f2f"
            }
            color = severity_colors.get(severity, "#f44336")
            
            events_html += f"""
            <div class="event-item" style="margin: 15px 0; padding: 15px; background: white; border-left: 4px solid {color};">
                <h4 style="margin: 0 0 10px 0;">Event {i} - {severity.name}</h4>
                <p style="margin: 5px 0;"><strong>Time:</strong> {time_str}</p>
                <p style="margin: 5px 0;"><strong>Agent:</strong> {agent_id}</p>
                <p style="margin: 5px 0;"><strong>Token:</strong> {token_id}</p>
                <p style="margin: 5px 0;"><strong>Action:</strong> {event_type.upper()}</p>
                <p style="margin: 5px 0; word-break: break-all;"><strong>Path:</strong> {path}</p>
            </div>
            """
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px 5px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; }}
        .summary {{ background: white; padding: 15px; margin: 15px 0; border-radius: 5px; }}
        .footer {{ margin-top: 20px; padding: 15px; background: #f1f1f1; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>🚨 HoneyGrid Alert Digest</h2>
            <p style="margin: 0;">Total Events: {len(events)}</p>
        </div>
        <div class="content">
            {logo_html}
            <div class="summary">
                <h3>Summary by Severity</h3>
                <ul>
                    {severity_summary}
                </ul>
            </div>
            <h3>Event Details</h3>
            {events_html}
        </div>
        <div class="footer">
            <p>This is an automated digest from HoneyGrid distributed honeytoken monitoring system.</p>
            <p style="margin: 0;">Do not reply to this email.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
