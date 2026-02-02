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
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
</head>
<body style="margin:0; padding:0; background:#f5f7fb;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f5f7fb;">
        <tr>
            <td align="center" style="padding:24px;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="620" style="max-width:620px; background:#ffffff; border-radius:12px; overflow:hidden; border:1px solid #e6eaf2;">
                    <tr>
                        <td style="background:{color}; padding:18px 22px; color:#ffffff; font-family:Segoe UI, Arial, sans-serif;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size:18px; font-weight:700;">HoneyGrid Alert</td>
                                    <td align="right" style="font-size:12px;">
                                        <span style="background:rgba(255,255,255,0.2); padding:4px 10px; border-radius:999px;">Severity: {severity.name}</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:20px 22px; font-family:Segoe UI, Arial, sans-serif; color:#111827;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding-bottom:14px;">{logo_html}</td>
                                </tr>
                                <tr>
                                    <td style="border-left:4px solid {color}; padding:8px 12px; background:#f8fafc; border-radius:8px; font-size:13px; color:#374151;">
                                        A honeytoken was triggered. Review the details below.
                                    </td>
                                </tr>
                            </table>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px; border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
                                <tr><td style="padding:10px 14px; background:#ffffff; border-bottom:1px solid #eef2f7;"><strong>Time</strong><br />{time_str}</td></tr>
                                <tr><td style="padding:10px 14px; background:#ffffff; border-bottom:1px solid #eef2f7;"><strong>Agent</strong><br />{agent_id}</td></tr>
                                <tr><td style="padding:10px 14px; background:#ffffff; border-bottom:1px solid #eef2f7;"><strong>Token</strong><br />{token_id}</td></tr>
                                <tr><td style="padding:10px 14px; background:#ffffff; border-bottom:1px solid #eef2f7;"><strong>Action</strong><br />{event_type.upper()}</td></tr>
                                <tr><td style="padding:10px 14px; background:#ffffff;"><strong>Path</strong><br /><span style="font-family:Consolas, monospace; font-size:12px; word-break:break-all;">{path}</span></td></tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:14px 22px 20px; font-family:Segoe UI, Arial, sans-serif; font-size:12px; color:#6b7280;">
                            This is an automated alert from HoneyGrid. Do not reply to this email.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
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
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
</head>
<body style="margin:0; padding:0; background:#f5f7fb;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="background:#f5f7fb;">
        <tr>
            <td align="center" style="padding:24px;">
                <table role="presentation" cellpadding="0" cellspacing="0" width="720" style="max-width:720px; background:#ffffff; border-radius:12px; overflow:hidden; border:1px solid #e6eaf2;">
                    <tr>
                        <td style="background:#1f2937; padding:18px 22px; color:#ffffff; font-family:Segoe UI, Arial, sans-serif;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="font-size:18px; font-weight:700;">HoneyGrid Alert Digest</td>
                                    <td align="right" style="font-size:12px;">Total Events: {len(events)}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:20px 22px; font-family:Segoe UI, Arial, sans-serif; color:#111827;">
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center" style="padding-bottom:14px;">{logo_html}</td>
                                </tr>
                            </table>
                            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb; border-radius:10px; overflow:hidden;">
                                <tr>
                                    <td style="padding:12px 14px; background:#ffffff;">
                                        <strong>Summary by Severity</strong>
                                        <ul style="margin: 8px 0 0; padding-left: 18px;">{severity_summary}</ul>
                                    </td>
                                </tr>
                            </table>
                            <div style="margin-top:16px; font-size:14px; font-weight:600;">Event Details</div>
                            <div style="margin-top:8px;">{events_html}</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:14px 22px 20px; font-family:Segoe UI, Arial, sans-serif; font-size:12px; color:#6b7280;">
                            This is an automated digest from HoneyGrid. Do not reply to this email.
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""
        return html
