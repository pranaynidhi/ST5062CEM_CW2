#!/usr/bin/env python3
"""
Unit tests for enhanced alert frame features.
Tests dropdown filters, multi-value filtering, and sorting.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import time
import tempfile

# Try to import tkinter, skip tests if not available
try:
    import tkinter as tk
    from tkinter import ttk
    HAS_TKINTER = True
except Exception:
    HAS_TKINTER = False

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gui_tk.alert_frame import AlertFrame
from server.db import DatabaseManager


@unittest.skipIf(not HAS_TKINTER, "Tkinter not available in this environment")
class TestAlertFrameFilters(unittest.TestCase):
    """Test alert frame dropdown filters."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test database
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_file.close()

        self.db = DatabaseManager(self.temp_file.name, "test_password")
        self.db.connect()

        # Create root window
        self.root = tk.Tk()
        self.root.withdraw()

        # Create alert frame
        self.frame = AlertFrame(self.root, self.db)

        # Add test data
        self._add_test_events()

    def tearDown(self):
        """Clean up test fixtures."""
        self.frame.set_database(None)
        self.root.destroy()
        self.db.close()

        # Clean up temp file
        import os
        os.unlink(self.temp_file.name)

    def _add_test_events(self):
        """Add test events to database."""
        self.db.register_agent("agent-001", "host1", "192.168.1.1")
        self.db.register_agent("agent-002", "host2", "192.168.1.2")

        # Event 1: opened (critical)
        self.db.insert_event(
            agent_id="agent-001",
            token_id="token-abc123",
            path="C:\\honeytokens\\secret.docx",
            event_type="opened",
            nonce="nonce-001",
            data={"user": "attacker"},
        )

        # Event 2: modified (high)
        self.db.insert_event(
            agent_id="agent-002",
            token_id="token-def456",
            path="C:\\honeytokens\\passwords.txt",
            event_type="modified",
            nonce="nonce-002",
            data={"user": "attacker"},
        )

        # Event 3: created (low)
        self.db.insert_event(
            agent_id="agent-001",
            token_id="token-ghi789",
            path="C:\\honeytokens\\newfile.txt",
            event_type="created",
            nonce="nonce-003",
            data={"user": "system"},
        )

        # Event 4: deleted (high)
        self.db.insert_event(
            agent_id="agent-002",
            token_id="token-abc123",
            path="C:\\honeytokens\\secret.docx",
            event_type="deleted",
            nonce="nonce-004",
            data={"user": "defender"},
        )

    def test_dropdown_filter_agent_single(self):
        """Test filtering by single agent."""
        self.frame.refresh()

        # Set agent filter to "agent-001"
        self.frame.search_vars["agent"].set("agent-001")
        self.frame.apply_filter()

        # Should have 2 events from agent-001
        self.assertEqual(len(self.frame.filtered_events), 2)
        for event in self.frame.filtered_events:
            self.assertEqual(event["agent_id"], "agent-001")

    def test_dropdown_filter_agent_multiple(self):
        """Test filtering by multiple agents."""
        self.frame.refresh()

        # Set agent filter to "agent-001, agent-002"
        self.frame.search_vars["agent"].set("agent-001, agent-002")
        self.frame.apply_filter()

        # Should have all 4 events
        self.assertEqual(len(self.frame.filtered_events), 4)

    def test_dropdown_filter_token_single(self):
        """Test filtering by single token."""
        self.frame.refresh()

        # Set token filter to "token-abc123"
        self.frame.search_vars["token"].set("token-abc123")
        self.frame.apply_filter()

        # Should have 2 events with token-abc123
        self.assertEqual(len(self.frame.filtered_events), 2)
        for event in self.frame.filtered_events:
            self.assertEqual(event["token_id"], "token-abc123")

    def test_dropdown_filter_type_single(self):
        """Test filtering by single event type."""
        self.frame.refresh()

        # Set type filter to "opened"
        self.frame.search_vars["type"].set("opened")
        self.frame.apply_filter()

        # Should have 1 event with type "opened"
        self.assertEqual(len(self.frame.filtered_events), 1)
        self.assertEqual(self.frame.filtered_events[0]["event_type"], "opened")

    def test_dropdown_filter_type_multiple(self):
        """Test filtering by multiple event types."""
        self.frame.refresh()

        # Set type filter to "opened, modified, deleted"
        self.frame.search_vars["type"].set("opened, modified, deleted")
        self.frame.apply_filter()

        # Should have 3 events
        self.assertEqual(len(self.frame.filtered_events), 3)
        types = {e["event_type"] for e in self.frame.filtered_events}
        self.assertEqual(types, {"opened", "modified", "deleted"})

    def test_dropdown_filter_combined(self):
        """Test filtering by multiple criteria."""
        self.frame.refresh()

        # Filter agent-001 + type opened
        self.frame.search_vars["agent"].set("agent-001")
        self.frame.search_vars["type"].set("opened")
        self.frame.apply_filter()

        # Should have 1 event (agent-001, opened)
        self.assertEqual(len(self.frame.filtered_events), 1)
        self.assertEqual(self.frame.filtered_events[0]["agent_id"], "agent-001")
        self.assertEqual(self.frame.filtered_events[0]["event_type"], "opened")

    def test_path_filter_substring(self):
        """Test filtering by path substring."""
        self.frame.refresh()

        # Filter path containing "secret"
        self.frame.search_vars["path"].set("secret")
        self.frame.apply_filter()

        # Should have 2 events with "secret" in path
        self.assertEqual(len(self.frame.filtered_events), 2)
        for event in self.frame.filtered_events:
            self.assertIn("secret", event["path"].lower())

    def test_empty_filter_shows_all(self):
        """Test that empty filter shows all events."""
        self.frame.refresh()

        # Clear all filters
        for var in self.frame.search_vars.values():
            var.set("")

        self.frame.apply_filter()

        # Should have all 4 events
        self.assertEqual(len(self.frame.filtered_events), 4)

    def test_dropdown_auto_population(self):
        """Test that dropdowns auto-populate from events."""
        self.frame.refresh()

        # Check agent dropdown
        agent_values = self.frame.agent_combo["values"]
        self.assertIn("", agent_values)  # Empty option
        self.assertIn("agent-001", agent_values)
        self.assertIn("agent-002", agent_values)

        # Check token dropdown
        token_values = self.frame.token_combo["values"]
        self.assertIn("", token_values)
        self.assertIn("token-abc123", token_values)
        self.assertIn("token-def456", token_values)

    def test_filter_case_insensitive(self):
        """Test that filtering is case-insensitive."""
        self.frame.refresh()

        # Set filter with uppercase
        self.frame.search_vars["agent"].set("AGENT-001")
        self.frame.apply_filter()

        # Should still find agent-001 (lowercase)
        self.assertEqual(len(self.frame.filtered_events), 2)
        self.assertEqual(self.frame.filtered_events[0]["agent_id"], "agent-001")

    def test_filter_with_whitespace(self):
        """Test that whitespace is handled correctly."""
        self.frame.refresh()

        # Set filter with extra whitespace
        self.frame.search_vars["agent"].set("  agent-001  ,  agent-002  ")
        self.frame.apply_filter()

        # Should handle whitespace correctly
        self.assertEqual(len(self.frame.filtered_events), 4)


@unittest.skipIf(not HAS_TKINTER, "Tkinter not available in this environment")
class TestAlertFrameSorting(unittest.TestCase):
    """Test alert frame sorting functionality."""

    def setUp(self):
        """Set up test fixtures."""        # Skip if Tkinter not available (CI environment)
        try:
            # Test if Tkinter can initialize
            test_root = tk.Tk()
            test_root.destroy()
        except Exception as e:
            self.skipTest(f"Tkinter not available: {e}")
        # Create test database
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_file.close()

        self.db = DatabaseManager(self.temp_file.name, "test_password")
        self.db.connect()

        # Create root window
        self.root = tk.Tk()
        self.root.withdraw()

        # Create alert frame
        self.frame = AlertFrame(self.root, self.db)

        # Add test data
        self._add_test_events()

    def tearDown(self):
        """Clean up test fixtures."""
        self.frame.set_database(None)
        self.root.destroy()
        self.db.close()

        # Clean up temp file
        import os
        os.unlink(self.temp_file.name)

    def _add_test_events(self):
        """Add test events with known order."""
        self.db.register_agent("agent-001", "host1", "192.168.1.1")
        self.db.register_agent("agent-002", "host2", "192.168.1.2")
        self.db.register_agent("agent-003", "host3", "192.168.1.3")

        # Add events with different timestamps
        for i, (agent, token, event_type) in enumerate([
            ("agent-003", "token-abc", "created"),
            ("agent-001", "token-def", "opened"),
            ("agent-002", "token-ghi", "modified"),
        ]):
            self.db.insert_event(
                agent_id=agent,
                token_id=token,
                path=f"C:\\honeytokens\\file{i}.txt",
                event_type=event_type,
                nonce=f"nonce-{i:03d}",
                timestamp=int(time.time()) + i,  # Incremental timestamps
            )

    def test_sort_by_agent_ascending(self):
        """Test sorting by agent in ascending order."""
        self.frame.refresh()

        # Trigger sort by agent
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_column, "agent")
        self.assertEqual(self.frame.sort_order, "ascending")

    def test_sort_by_agent_descending(self):
        """Test sorting by agent in descending order."""
        self.frame.refresh()

        # First sort
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_order, "ascending")

        # Second sort (toggle to descending)
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_order, "descending")

    def test_sort_cycle_normal_ascending_descending(self):
        """Test that sort cycles through all states."""
        self.frame.refresh()

        # Initial state
        self.assertEqual(self.frame.sort_order, "normal")

        # First click: ascending
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_order, "ascending")

        # Second click: descending
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_order, "descending")

        # Third click: back to normal
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_order, "normal")

    def test_sort_column_switching(self):
        """Test switching between sort columns."""
        self.frame.refresh()

        # Sort by agent
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_column, "agent")
        self.assertEqual(self.frame.sort_order, "ascending")

        # Switch to token
        self.frame._sort_column("token")
        self.assertEqual(self.frame.sort_column, "token")
        # Should reset to ascending when changing column
        self.assertEqual(self.frame.sort_order, "ascending")

    def test_sort_indicator_update(self):
        """Test that sort indicators are updated in headers."""
        self.frame.refresh()

        # Sort by agent ascending
        self.frame._sort_column("agent")
        self.frame._update_header_labels()

        # Check header text contains sort indicator
        agent_heading = self.frame.tree.heading("agent", "text")
        self.assertIn("↑", agent_heading)

        # Sort by agent descending
        self.frame._sort_column("agent")
        self.frame._update_header_labels()

        agent_heading = self.frame.tree.heading("agent", "text")
        self.assertIn("↓", agent_heading)

        # Sort by agent normal
        self.frame._sort_column("agent")
        self.frame._update_header_labels()

        agent_heading = self.frame.tree.heading("agent", "text")
        self.assertNotIn("↑", agent_heading)
        self.assertNotIn("↓", agent_heading)


@unittest.skipIf(not HAS_TKINTER, "Tkinter not available in this environment")
class TestAlertFrameIntegration(unittest.TestCase):
    """Integration tests for alert frame features."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test database
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_file.close()

        self.db = DatabaseManager(self.temp_file.name, "test_password")
        self.db.connect()

        # Create root window
        self.root = tk.Tk()
        self.root.withdraw()

        # Create alert frame
        self.frame = AlertFrame(self.root, self.db)

        # Add test data
        self._add_test_events()

    def tearDown(self):
        """Clean up test fixtures."""
        self.frame.set_database(None)
        self.root.destroy()
        self.db.close()

        # Clean up temp file
        import os
        os.unlink(self.temp_file.name)

    def _add_test_events(self):
        """Add test events."""
        agents = ["agent-001", "agent-002", "agent-003"]
        tokens = ["token-abc", "token-def", "token-ghi"]
        types = ["created", "modified", "opened"]

        for i, (agent, token, event_type) in enumerate(
            zip(agents, tokens, types)
        ):
            self.db.register_agent(agent, f"host{i+1}", f"192.168.1.{i+1}")

            self.db.insert_event(
                agent_id=agent,
                token_id=token,
                path=f"C:\\honeytokens\\file{i}.txt",
                event_type=event_type,
                nonce=f"nonce-{i:03d}",
            )

    def test_filter_then_sort(self):
        """Test filtering and then sorting."""
        self.frame.refresh()

        # Filter to agent-001 and agent-002
        self.frame.search_vars["agent"].set("agent-001, agent-002")
        self.frame.apply_filter()

        # Should have 2 events
        self.assertEqual(len(self.frame.filtered_events), 2)

        # Sort by agent
        self.frame._sort_column("agent")
        self.frame._populate_tree()

        # Verify tree is populated
        tree_items = self.frame.tree.get_children()
        self.assertEqual(len(tree_items), 2)

    def test_sort_then_filter(self):
        """Test sorting and then filtering."""
        self.frame.refresh()

        # Sort by agent
        self.frame._sort_column("agent")

        # Filter by type "opened"
        self.frame.search_vars["type"].set("opened")
        self.frame.apply_filter()

        # Should have 1 event
        self.assertEqual(len(self.frame.filtered_events), 1)

        # Verify tree is sorted
        self.frame._populate_tree()
        tree_items = self.frame.tree.get_children()
        self.assertEqual(len(tree_items), 1)

    def test_clear_filter_preserves_sort(self):
        """Test that clearing filter preserves sort state."""
        self.frame.refresh()

        # Sort by agent
        self.frame._sort_column("agent")
        self.assertEqual(self.frame.sort_column, "agent")

        # Apply filter
        self.frame.search_vars["agent"].set("agent-001")
        self.frame.apply_filter()

        # Clear filter
        self.frame.clear_filter()

        # Sort state should be preserved
        self.assertEqual(self.frame.sort_column, "agent")

    def test_count_label_updates(self):
        """Test that event count label updates correctly."""
        self.frame.refresh()

        # Initial count should be 3
        count_text = self.frame.count_label.cget("text")
        self.assertIn("3", count_text)

        # Filter to agent-001
        self.frame.search_vars["agent"].set("agent-001")
        self.frame.apply_filter()

        # Count should be 1
        count_text = self.frame.count_label.cget("text")
        self.assertIn("1", count_text)

        # Clear filter
        self.frame.clear_filter()

        # Count should be back to 3
        count_text = self.frame.count_label.cget("text")
        self.assertIn("3", count_text)


if __name__ == "__main__":
    unittest.main()
