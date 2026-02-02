#!/usr/bin/env python3
"""
HoneyGrid Theme Manager
Provides light and dark theme support with dynamic switching.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Theme configuration path
CONFIG_DIR = Path("config")
THEME_CONFIG_FILE = CONFIG_DIR / "theme.json"

# Define color palettes
LIGHT_THEME = {
    "name": "light",
    "bg": "#f0f0f0",
    "fg": "#000000",
    "frame_bg": "#ffffff",
    "button_bg": "#e0e0e0",
    "button_fg": "#000000",
    "entry_bg": "#ffffff",
    "entry_fg": "#000000",
    "text_bg": "#ffffff",
    "text_fg": "#000000",
    "tree_bg": "#ffffff",
    "tree_fg": "#000000",
    "tree_field_bg": "#ffffff",
    "tree_field_fg": "#000000",
    "menubar_bg": "#f0f0f0",
    "menubar_fg": "#000000",
    "menu_bg": "#ffffff",
    "menu_fg": "#000000",
    "label_bg": "#f0f0f0",
    "label_fg": "#000000",
    "highlight": "#0078d4",
    "highlight_bg": "#e8f4f8",
    "error_bg": "#f8d7da",
    "error_fg": "#721c24",
    "warning_bg": "#fff3cd",
    "warning_fg": "#856404",
    "success_bg": "#d4edda",
    "success_fg": "#155724",
    "canvas_bg": "#ffffff",
    "statusbar_bg": "#e0e0e0",
    "statusbar_fg": "#000000",
}

DARK_THEME = {
    "name": "dark",
    "bg": "#1e1e1e",
    "fg": "#e0e0e0",
    "frame_bg": "#2d2d2d",
    "button_bg": "#3d3d3d",
    "button_fg": "#e0e0e0",
    "entry_bg": "#3d3d3d",
    "entry_fg": "#e0e0e0",
    "text_bg": "#2d2d2d",
    "text_fg": "#e0e0e0",
    "tree_bg": "#2d2d2d",
    "tree_fg": "#e0e0e0",
    "tree_field_bg": "#3d3d3d",
    "tree_field_fg": "#e0e0e0",
    "menubar_bg": "#1e1e1e",
    "menubar_fg": "#e0e0e0",
    "menu_bg": "#2d2d2d",
    "menu_fg": "#e0e0e0",
    "label_bg": "#1e1e1e",
    "label_fg": "#e0e0e0",
    "highlight": "#0078d4",
    "highlight_bg": "#1a3a4a",
    "error_bg": "#3d1f24",
    "error_fg": "#ff8a8a",
    "warning_bg": "#3d2d1a",
    "warning_fg": "#ffa500",
    "success_bg": "#1f3d24",
    "success_fg": "#6eff6e",
    "canvas_bg": "#1e1e1e",
    "statusbar_bg": "#2d2d2d",
    "statusbar_fg": "#e0e0e0",
}


class ThemeManager:
    """Manages application themes and dynamic switching."""

    def __init__(self, default_theme: str = "light"):
        """
        Initialize theme manager.

        Args:
            default_theme: Default theme name ("light" or "dark")
        """
        self.current_theme = default_theme
        self.themes = {"light": LIGHT_THEME, "dark": DARK_THEME}
        self.callbacks = []  # Callbacks for theme changes

        # Create config directory if needed
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Load saved theme preference
        self._load_theme_preference()

    def _load_theme_preference(self):
        """Load saved theme preference from config file."""
        try:
            if THEME_CONFIG_FILE.exists():
                with open(THEME_CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    saved_theme = config.get("theme", "light")
                    if saved_theme in self.themes:
                        self.current_theme = saved_theme
                        logger.info(f"Loaded theme preference: {self.current_theme}")
        except Exception as e:
            logger.warning(f"Failed to load theme preference: {e}")

    def _save_theme_preference(self):
        """Save current theme preference to config file."""
        try:
            config = {"theme": self.current_theme}
            with open(THEME_CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Saved theme preference: {self.current_theme}")
        except Exception as e:
            logger.error(f"Failed to save theme preference: {e}")

    def get_theme(self) -> Dict[str, str]:
        """
        Get current theme dictionary.

        Returns:
            Theme color dictionary
        """
        return self.themes.get(self.current_theme, self.themes["light"]).copy()

    def get_color(self, key: str) -> str:
        """
        Get a specific color from current theme.

        Args:
            key: Color key (e.g., "bg", "fg", "highlight")

        Returns:
            Color hex code
        """
        theme = self.get_theme()
        return theme.get(key, "#000000")

    def set_theme(self, theme_name: str):
        """
        Switch to a different theme.

        Args:
            theme_name: Theme name ("light" or "dark")
        """
        if theme_name not in self.themes:
            logger.warning(f"Unknown theme: {theme_name}")
            return

        if self.current_theme == theme_name:
            return  # Already on this theme

        self.current_theme = theme_name
        self._save_theme_preference()

        # Notify all registered callbacks
        for callback in self.callbacks:
            try:
                callback(self.get_theme())
            except Exception as e:
                logger.error(f"Error in theme change callback: {e}")

        logger.info(f"Theme switched to: {theme_name}")

    def toggle_theme(self):
        """Toggle between light and dark theme."""
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.set_theme(new_theme)

    def register_callback(self, callback):
        """
        Register a callback for theme changes.

        Args:
            callback: Function to call when theme changes (receives theme dict)
        """
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def unregister_callback(self, callback):
        """
        Unregister a theme change callback.

        Args:
            callback: Callback function to remove
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def is_dark_mode(self) -> bool:
        """Check if dark mode is currently active."""
        return self.current_theme == "dark"

    def is_light_mode(self) -> bool:
        """Check if light mode is currently active."""
        return self.current_theme == "light"


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager(default_theme: str = "light") -> ThemeManager:
    """
    Get or create the global theme manager instance.

    Args:
        default_theme: Default theme for first initialization

    Returns:
        ThemeManager instance
    """
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager(default_theme)
    return _theme_manager


def apply_theme_to_widget(widget, theme: Dict[str, str], widget_type: str = "frame"):
    """
    Apply theme colors to a tkinter widget.

    Args:
        widget: Tkinter widget to theme
        theme: Theme dictionary
        widget_type: Type of widget (frame, button, label, text, etc.)
    """
    import tkinter as tk

    try:
        if widget_type in ("frame", "labelframe"):
            widget.config(bg=theme.get("frame_bg", theme["bg"]))

        elif widget_type == "label":
            widget.config(bg=theme.get("label_bg", theme["bg"]), fg=theme.get("label_fg", theme["fg"]))

        elif widget_type == "button":
            widget.config(bg=theme.get("button_bg"), fg=theme.get("button_fg"))

        elif widget_type == "entry":
            widget.config(bg=theme.get("entry_bg", theme["bg"]), fg=theme.get("entry_fg", theme["fg"]))

        elif widget_type == "text":
            widget.config(bg=theme.get("text_bg", theme["bg"]), fg=theme.get("text_fg", theme["fg"]))

        elif widget_type == "treeview":
            widget.config(background=theme.get("tree_bg"), foreground=theme.get("tree_fg"))

        elif widget_type == "canvas":
            widget.config(bg=theme.get("canvas_bg", theme["bg"]))

        elif widget_type == "listbox":
            widget.config(bg=theme.get("entry_bg", theme["bg"]), fg=theme.get("entry_fg", theme["fg"]))

    except Exception as e:
        logger.warning(f"Could not apply theme to widget: {e}")


if __name__ == "__main__":
    # Test theme manager
    print("Theme Manager Test")
    print("=" * 60)

    tm = ThemeManager("light")

    print(f"\n1. Current theme: {tm.current_theme}")
    print(f"   Light mode: {tm.is_light_mode()}")
    print(f"   Dark mode: {tm.is_dark_mode()}")

    print("\n2. Getting colors from light theme:")
    theme = tm.get_theme()
    print(f"   Background: {theme['bg']}")
    print(f"   Foreground: {theme['fg']}")
    print(f"   Highlight: {theme['highlight']}")

    print("\n3. Switching to dark theme...")
    tm.toggle_theme()
    print(f"   Current theme: {tm.current_theme}")
    print(f"   Dark mode: {tm.is_dark_mode()}")

    print("\n4. Dark theme colors:")
    theme = tm.get_theme()
    print(f"   Background: {theme['bg']}")
    print(f"   Foreground: {theme['fg']}")
    print(f"   Highlight: {theme['highlight']}")

    print("\n5. Testing callback...")

    def on_theme_change(new_theme):
        print(f"   Theme changed! New bg: {new_theme['bg']}")

    tm.register_callback(on_theme_change)
    print("   Toggling theme...")
    tm.toggle_theme()

    print("\n" + "=" * 60)
    print("✓ Theme manager test completed")
