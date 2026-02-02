#!/usr/bin/env python3
"""
Integration tests for file system monitoring.
Tests FSMonitor with real file operations.
"""

import pytest
import time
import os
import tempfile
import shutil
from pathlib import Path
import sys
import multiprocessing

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.monitor import FSMonitor, MonitorEvent


@pytest.fixture
def temp_watch_dir():
    """Create a temporary directory for watching."""
    temp_dir = tempfile.mkdtemp(prefix="honeygrid_test_")
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


class TestFileMonitoring:
    """Test file system monitoring."""

    def test_monitor_detects_file_creation(self, temp_watch_dir):
        """Test that monitor detects new file creation."""
        # Create queue
        event_queue = multiprocessing.Manager().Queue()

        # Create and start monitor
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(temp_watch_dir, token_id="test-token-001")
        monitor.start()

        try:
            # Wait for monitor to initialize
            time.sleep(1)

            # Create a file
            test_file = os.path.join(temp_watch_dir, "test_file.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            # Wait for event
            time.sleep(2)

            # Check queue for event
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            # Should have at least one creation event
            assert len(events) > 0

            # Find creation event
            creation_events = [
                e for e in events if e.event_type in ("created", "modified")
            ]
            assert len(creation_events) > 0

            # Verify event details
            event = creation_events[0]
            assert event.token_id == "test-token-001"
            assert "test_file.txt" in event.path

        finally:
            monitor.stop()

    def test_monitor_detects_file_modification(self, temp_watch_dir):
        """Test that monitor detects file modifications."""
        # Create initial file
        test_file = os.path.join(temp_watch_dir, "test_modify.txt")
        with open(test_file, "w") as f:
            f.write("initial content")

        # Create queue and monitor
        event_queue = multiprocessing.Manager().Queue()
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(temp_watch_dir, token_id="test-token-002")
        monitor.start()

        try:
            time.sleep(1)

            # Modify file
            with open(test_file, "a") as f:
                f.write("\nmodified content")

            time.sleep(2)

            # Check for modification event
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            assert len(events) > 0

            # Find modification event
            mod_events = [e for e in events if e.event_type == "modified"]
            assert len(mod_events) > 0

            event = mod_events[0]
            assert "test_modify.txt" in event.path

        finally:
            monitor.stop()

    def test_monitor_detects_file_deletion(self, temp_watch_dir):
        """Test that monitor detects file deletion."""
        # Create file
        test_file = os.path.join(temp_watch_dir, "test_delete.txt")
        with open(test_file, "w") as f:
            f.write("to be deleted")

        # Create monitor
        event_queue = multiprocessing.Manager().Queue()
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(temp_watch_dir, token_id="test-token-003")
        monitor.start()

        try:
            time.sleep(1)

            # Delete file
            os.remove(test_file)

            time.sleep(2)

            # Check for deletion event
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            assert len(events) > 0

            # Find deletion event
            del_events = [e for e in events if e.event_type == "deleted"]
            assert len(del_events) > 0

            event = del_events[0]
            assert "test_delete.txt" in event.path

        finally:
            monitor.stop()

    def test_monitor_detects_file_move(self, temp_watch_dir):
        """Test that monitor detects file moves."""
        # Create file
        src_file = os.path.join(temp_watch_dir, "test_move_src.txt")
        dst_file = os.path.join(temp_watch_dir, "test_move_dst.txt")

        with open(src_file, "w") as f:
            f.write("move me")

        # Create monitor
        event_queue = multiprocessing.Manager().Queue()
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(temp_watch_dir, token_id="test-token-004")
        monitor.start()

        try:
            time.sleep(1)

            # Move file
            shutil.move(src_file, dst_file)

            time.sleep(2)

            # Check for move event
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            assert len(events) > 0

            # Should have moved event (or deleted + created)
            move_events = [
                e for e in events if e.event_type in ("moved", "deleted", "created")
            ]
            assert len(move_events) > 0

        finally:
            monitor.stop()

    def test_monitor_multiple_paths(self, temp_watch_dir):
        """Test monitoring multiple paths."""
        # Create subdirectories
        dir1 = os.path.join(temp_watch_dir, "dir1")
        dir2 = os.path.join(temp_watch_dir, "dir2")
        os.makedirs(dir1)
        os.makedirs(dir2)

        # Create monitor
        event_queue = multiprocessing.Manager().Queue()
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(dir1, token_id="token-dir1")
        monitor.add_watch_path(dir2, token_id="token-dir2")
        monitor.start()

        try:
            time.sleep(1)

            # Create files in both directories
            file1 = os.path.join(dir1, "file1.txt")
            file2 = os.path.join(dir2, "file2.txt")

            with open(file1, "w") as f:
                f.write("dir1 content")

            with open(file2, "w") as f:
                f.write("dir2 content")

            time.sleep(2)

            # Check events
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            assert len(events) > 0

            # Should have events from both directories
            dir1_events = [e for e in events if "dir1" in e.path]
            dir2_events = [e for e in events if "dir2" in e.path]

            assert len(dir1_events) > 0
            assert len(dir2_events) > 0

            # Verify token IDs
            assert any(e.token_id == "token-dir1" for e in dir1_events)
            assert any(e.token_id == "token-dir2" for e in dir2_events)

        finally:
            monitor.stop()

    def test_monitor_ignores_directories(self, temp_watch_dir):
        """Test that monitor can distinguish files from directories."""
        event_queue = multiprocessing.Manager().Queue()
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(temp_watch_dir, token_id="test-token-005")
        monitor.start()

        try:
            time.sleep(1)

            # Create subdirectory
            subdir = os.path.join(temp_watch_dir, "subdir")
            os.makedirs(subdir)

            time.sleep(2)

            # Check events
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            # Should have events for directory
            dir_events = [e for e in events if e.is_directory]
            assert len(dir_events) > 0

        finally:
            monitor.stop()


class TestMonitorPerformance:
    """Test monitor performance and stability."""

    def test_monitor_handles_rapid_changes(self, temp_watch_dir):
        """Test that monitor handles rapid file changes."""
        event_queue = multiprocessing.Manager().Queue()
        monitor = FSMonitor(event_queue)
        monitor.add_watch_path(temp_watch_dir, token_id="test-token-006")
        monitor.start()

        try:
            time.sleep(1)

            # Create many files rapidly
            for i in range(10):
                test_file = os.path.join(temp_watch_dir, f"rapid_{i}.txt")
                with open(test_file, "w") as f:
                    f.write(f"content {i}")

            time.sleep(3)

            # Should have captured most/all events
            events = []
            while not event_queue.empty():
                events.append(event_queue.get_nowait())

            # Should have at least some events (may not catch all due to timing)
            assert len(events) > 0

        finally:
            monitor.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
