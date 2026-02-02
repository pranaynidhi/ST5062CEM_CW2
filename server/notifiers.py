#!/usr/bin/env python3
"""
Compatibility shim for HoneyGrid notification package.

This avoids import ambiguity between the legacy module and the
server/notifiers/ package by treating this module as a package and
re-exporting the package symbols.
"""

from pathlib import Path
import importlib

# Treat this module as a package to support relative imports.
__path__ = [str(Path(__file__).with_name("notifiers"))]

_base = importlib.import_module("server.notifiers.base")
_email = importlib.import_module("server.notifiers.email_notifier")
_discord = importlib.import_module("server.notifiers.discord_notifier")

Notifier = _base.Notifier
NotificationConfig = _base.NotificationConfig
Severity = _base.Severity
EmailNotifier = _email.EmailNotifier
DiscordNotifier = _discord.DiscordNotifier

__all__ = [
    "Notifier",
    "NotificationConfig",
    "Severity",
    "EmailNotifier",
    "DiscordNotifier",
]
