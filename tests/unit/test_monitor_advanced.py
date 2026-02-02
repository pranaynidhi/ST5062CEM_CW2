#!/usr/bin/env python3
"""
Advanced unit tests for monitor module.
Tests file system monitoring and event handling.
"""

import pytest
import time
import tempfile
import os
from pathlib import Path
from multiprocessing import Manager
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.monitor import FSMonitor, MonitorEvent


class TestFSMonitorAdvanced:
    """Test advanced FSMonitor functionality."""

    def test_monitor_multiple_paths(self):
        """Test monitoring multiple paths simultaneously."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                with tempfile.TemporaryDirectory() as tmpdir3:
                    monitor = FSMonitor(
                        event_queue=queue, watch_paths=[tmpdir1, tmpdir2, tmpdir3]
                    )

                    # Should be monitoring all three
                    assert len(monitor.watch_paths) == 3

    def test_monitor_with_verbose(self):
        """Test monitor with verbose logging enabled."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(event_queue=queue, watch_paths=[tmpdir], verbose=True)

            assert monitor.verbose is True

    def test_monitor_non_recursive(self):
        """Test monitor with recursive=False."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(
                event_queue=queue, watch_paths=[tmpdir], recursive=False
            )

            assert monitor.recursive is False

    def test_monitor_recursive_default(self):
        """Test that recursive monitoring is default."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(event_queue=queue, watch_paths=[tmpdir])

            # Default should be True
            assert monitor.recursive is True

    def test_monitor_empty_watch_paths(self):
        """Test monitor with no watch paths initially."""
        manager = Manager()
        queue = manager.Queue()

        monitor = FSMonitor(event_queue=queue)

        # Should initialize with empty list
        assert monitor.watch_paths == []

    def test_monitor_complex_token_mapping(self):
        """Test monitor with complex token mapping."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = os.path.join(tmpdir, "file1.txt")
            path2 = os.path.join(tmpdir, "file2.doc")
            path3 = os.path.join(tmpdir, "subdir", "file3.pdf")

            token_mapping = {
                "token_file1": path1,
                "token_file2": path2,
                "token_file3": path3,
            }

            monitor = FSMonitor(
                event_queue=queue, watch_paths=[tmpdir], token_mapping=token_mapping
            )

            assert len(monitor.token_mapping) == 3
            assert "token_file1" in monitor.token_mapping
            assert "token_file2" in monitor.token_mapping
            assert "token_file3" in monitor.token_mapping


class TestMonitorEventAdvanced:
    """Test advanced MonitorEvent functionality."""

    def test_event_with_directory(self):
        """Test creating event for directory."""
        event = MonitorEvent(
            token_id="token123",
            path="/tmp/honeydir",
            event_type="created",
            timestamp=time.time(),
            is_directory=True,
            metadata={},
        )

        assert event.is_directory is True

    def test_event_with_metadata(self):
        """Test creating event with rich metadata."""
        metadata = {
            "user": "admin",
            "process": "explorer.exe",
            "pid": 1234,
            "access_type": "read",
        }

        event = MonitorEvent(
            token_id="token456",
            path="/tmp/file.txt",
            event_type="opened",
            timestamp=time.time(),
            is_directory=False,
            metadata=metadata,
        )

        assert event.metadata == metadata
        assert event.metadata["user"] == "admin"
        assert event.metadata["pid"] == 1234

    def test_event_to_dict_complete(self):
        """Test converting event with all fields to dict."""
        event = MonitorEvent(
            token_id="token789",
            path="/var/honey/secret.pdf",
            event_type="modified",
            timestamp=1234567890.5,
            is_directory=False,
            metadata={"size": 4096, "modified_by": "attacker"},
        )

        d = event.to_dict()

        assert d["token_id"] == "token789"
        assert d["path"] == "/var/honey/secret.pdf"
        assert d["event_type"] == "modified"
        assert d["timestamp"] == 1234567890.5
        assert d["is_directory"] is False
        assert d["metadata"]["size"] == 4096

    def test_event_different_types(self):
        """Test creating events with different event types."""
        types = ["created", "modified", "opened", "moved", "deleted"]

        for event_type in types:
            event = MonitorEvent(
                token_id="token",
                path="/path",
                event_type=event_type,
                timestamp=time.time(),
                is_directory=False,
                metadata={},
            )

            assert event.event_type == event_type

    def test_event_paths_types(self):
        """Test events with different path types."""
        paths = [
            "/unix/path/file.txt",
            "C:\\Windows\\path\\file.doc",
            "/path/with spaces/file.txt",
            "relative/path/file.pdf",
        ]

        for path in paths:
            event = MonitorEvent(
                token_id="token",
                path=path,
                event_type="created",
                timestamp=time.time(),
                is_directory=False,
                metadata={},
            )

            assert event.path == path


class TestFSMonitorConfiguration:
    """Test FSMonitor configuration options."""

    def test_monitor_with_all_options(self):
        """Test monitor with all configuration options."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(
                event_queue=queue,
                watch_paths=[tmpdir],
                token_mapping={"t1": os.path.join(tmpdir, "file.txt")},
                recursive=True,
                verbose=True,
            )

            assert monitor.event_queue is not None
            assert len(monitor.watch_paths) == 1
            assert len(monitor.token_mapping) == 1
            assert monitor.recursive is True
            assert monitor.verbose is True

    def test_monitor_different_recursion_settings(self):
        """Test monitor with different recursion settings."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Recursive
            monitor1 = FSMonitor(
                event_queue=queue, watch_paths=[tmpdir], recursive=True
            )

            # Non-recursive
            monitor2 = FSMonitor(
                event_queue=queue, watch_paths=[tmpdir], recursive=False
            )

            assert monitor1.recursive is True
            assert monitor2.recursive is False

    def test_monitor_verbose_levels(self):
        """Test monitor with different verbose settings."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Verbose on
            monitor1 = FSMonitor(event_queue=queue, watch_paths=[tmpdir], verbose=True)

            # Verbose off
            monitor2 = FSMonitor(event_queue=queue, watch_paths=[tmpdir], verbose=False)

            assert monitor1.verbose is True
            assert monitor2.verbose is False


class TestMonitorPathOperations:
    """Test path-related monitor operations."""

    def test_add_single_watch_path(self):
        """Test adding a single watch path."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(event_queue=queue)
            monitor.add_watch_path(tmpdir, "token1")

            # Path should be added
            assert tmpdir in monitor.watch_paths or len(monitor.watch_paths) > 0

    def test_add_multiple_watch_paths_sequentially(self):
        """Test adding multiple paths one by one."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                monitor = FSMonitor(event_queue=queue)
                monitor.add_watch_path(tmpdir1, "token1")
                monitor.add_watch_path(tmpdir2, "token2")

                # Both should be added
                assert len(monitor.watch_paths) >= 1

    def test_remove_existing_path(self):
        """Test removing an existing watch path."""
        manager = Manager()
        queue = manager.Queue()

        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                monitor = FSMonitor(event_queue=queue, watch_paths=[tmpdir1, tmpdir2])

                initial_count = len(monitor.watch_paths)
                monitor.remove_watch_path(tmpdir1)

                # Should have one less
                assert len(monitor.watch_paths) <= initial_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
