#!/usr/bin/env python3
"""
HoneyGrid Statistics Frame
Display statistics and metrics for events, agents, and tokens.
"""

import tkinter as tk
from tkinter import ttk
import time
from typing import Dict, List, Optional
from collections import Counter


class StatsFrame(ttk.Frame):
    """
    Statistics panel showing event metrics and analytics.
    """

    def __init__(self, parent, db=None):
        """
        Initialize stats frame.

        Args:
            parent: Parent widget
            db: Database manager
        """
        super().__init__(parent)

        self.db = db
        self.stats = {}

        # Build UI
        self._build_ui()

        # Initial refresh
        if self.db:
            self.refresh()

    def _build_ui(self):
        """Build user interface."""
        # Title and refresh button
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            header_frame, text="Statistics Dashboard", font=("Arial", 12, "bold")
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(header_frame, text="Refresh", command=self.refresh).pack(
            side=tk.RIGHT, padx=5
        )

        # Main stats container
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left column - Overview stats
        left_frame = ttk.LabelFrame(main_container, text="Overview", padding="10")
        left_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.overview_labels = {}
        overview_stats = [
            ("total_events", "Total Events"),
            ("total_agents", "Total Agents"),
            ("total_tokens", "Total Tokens"),
            ("events_24h", "Events (24h)"),
        ]

        for i, (key, label) in enumerate(overview_stats):
            ttk.Label(left_frame, text=f"{label}:", font=("Arial", 9, "bold")).grid(
                row=i, column=0, sticky=tk.W, pady=2
            )
            value_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
            value_label.grid(row=i, column=1, sticky=tk.E, padx=(10, 0), pady=2)
            self.overview_labels[key] = value_label

        # Right column - By Agent
        right_frame = ttk.LabelFrame(
            main_container, text="Events by Agent", padding="10"
        )
        right_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Scrollable listbox for agent stats
        agent_scroll = ttk.Scrollbar(right_frame)
        agent_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.agent_listbox = tk.Listbox(
            right_frame,
            yscrollcommand=agent_scroll.set,
            font=("Courier New", 9),
            height=8,
        )
        self.agent_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        agent_scroll.config(command=self.agent_listbox.yview)

        # Bottom left - By Event Type
        type_frame = ttk.LabelFrame(main_container, text="Events by Type", padding="10")
        type_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        type_scroll = ttk.Scrollbar(type_frame)
        type_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.type_listbox = tk.Listbox(
            type_frame,
            yscrollcommand=type_scroll.set,
            font=("Courier New", 9),
            height=6,
        )
        self.type_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        type_scroll.config(command=self.type_listbox.yview)

        # Bottom right - By Token
        token_frame = ttk.LabelFrame(main_container, text="Top Tokens", padding="10")
        token_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        token_scroll = ttk.Scrollbar(token_frame)
        token_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.token_listbox = tk.Listbox(
            token_frame,
            yscrollcommand=token_scroll.set,
            font=("Courier New", 9),
            height=6,
        )
        self.token_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        token_scroll.config(command=self.token_listbox.yview)

        # Configure grid weights
        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_rowconfigure(0, weight=1)
        main_container.grid_rowconfigure(1, weight=1)

    def set_database(self, db):
        """Set database connection."""
        self.db = db
        self.refresh()

    def refresh(self):
        """Refresh statistics from database."""
        if not self.db:
            return

        try:
            # Get basic stats from database
            db_stats = self.db.get_stats()

            # Update overview labels
            for key, label in self.overview_labels.items():
                value = db_stats.get(key, 0)
                label.config(text=str(value))

            # Get recent events for detailed breakdown
            events = self.db.get_recent_events(limit=1000)

            # Calculate events by agent
            agent_counts = Counter(e.get("agent_id", "Unknown") for e in events)
            self._update_listbox(
                self.agent_listbox,
                agent_counts,
                format_fn=lambda k, v: f"{k:<20} {v:>5} events",
            )

            # Calculate events by type
            type_counts = Counter(e.get("event_type", "Unknown") for e in events)
            self._update_listbox(
                self.type_listbox,
                type_counts,
                format_fn=lambda k, v: f"{k:<15} {v:>5} events",
            )

            # Calculate events by token (top 10)
            token_counts = Counter(e.get("token_id", "Unknown") for e in events)
            top_tokens = dict(token_counts.most_common(10))
            self._update_listbox(
                self.token_listbox,
                top_tokens,
                format_fn=lambda k, v: f"{k:<20} {v:>5} events",
            )

        except Exception as e:
            print(f"Failed to refresh stats: {e}")

    def _update_listbox(self, listbox, counts: Dict, format_fn=None):
        """
        Update a listbox with count data.

        Args:
            listbox: tk.Listbox to update
            counts: Dictionary of item counts
            format_fn: Optional formatting function
        """
        listbox.delete(0, tk.END)

        if not counts:
            listbox.insert(tk.END, "No data available")
            return

        # Sort by count descending
        sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)

        for key, value in sorted_items:
            if format_fn:
                text = format_fn(key, value)
            else:
                text = f"{key}: {value}"
            listbox.insert(tk.END, text)


if __name__ == "__main__":
    # Test the stats frame
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent))

    from server.db import DatabaseManager
    import tempfile

    # Create test database
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()

    db = DatabaseManager(temp_file.name, "test")
    db.connect()

    # Add test data
    db.register_agent("agent-001", "test-host-1", "192.168.1.100")
    db.register_agent("agent-002", "test-host-2", "192.168.1.101")

    for i in range(10):
        db.insert_event(
            agent_id=f"agent-00{(i % 2) + 1}",
            token_id=f"token-{(i % 3) + 1:03d}",
            path=f"C:\\honeytokens\\file{i}.txt",
            event_type=["created", "modified", "opened", "deleted"][i % 4],
            nonce=f"nonce-{i:03d}",
        )

    # Create GUI
    root = tk.Tk()
    root.title("Stats Frame Test")
    root.geometry("800x500")

    frame = StatsFrame(root, db)
    frame.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

    # Cleanup
    db.close()
    import os

    os.unlink(temp_file.name)
