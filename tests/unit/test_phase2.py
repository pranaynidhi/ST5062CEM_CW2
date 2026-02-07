#!/usr/bin/env python3
"""
Unit tests for enhanced monitoring: File Hash Tracker and Process Capture
"""

import pytest
import os
import tempfile
import hashlib
import time
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.monitor import FileHashTracker, MonitorEvent
from agent.process_info import ProcessCapture


class TestFileHashTracker:
    """Tests for FileHashTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a FileHashTracker instance."""
        return FileHashTracker()

    @pytest.fixture
    def temp_file(self):
        """Create a temporary file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Test content for hashing")
            temp_path = f.name
        yield temp_path
        # Cleanup
        try:
            os.unlink(temp_path)
        except:
            pass

    def test_calculate_hash(self, tracker, temp_file):
        """Test hash calculation."""
        hash1 = tracker.calculate_hash(temp_file)
        assert hash1 is not None
        assert len(hash1) == 64  # SHA256 hex is 64 chars
        assert hash1.isalnum()

    def test_calculate_hash_consistency(self, tracker, temp_file):
        """Test that hash calculation is consistent."""
        hash1 = tracker.calculate_hash(temp_file)
        hash2 = tracker.calculate_hash(temp_file)
        assert hash1 == hash2

    def test_calculate_hash_file_not_found(self, tracker):
        """Test hash calculation with non-existent file."""
        hash_result = tracker.calculate_hash("/nonexistent/file.txt")
        assert hash_result is None

    def test_store_hash(self, tracker, temp_file):
        """Test storing a hash."""
        hash_value = "abc123def456"
        stored = tracker.store_hash(temp_file, hash_value)
        assert stored == hash_value
        assert tracker.get_original_hash(temp_file) == hash_value

    def test_store_hash_calculate_if_none(self, tracker, temp_file):
        """Test storing hash by calculating if not provided."""
        stored = tracker.store_hash(temp_file)
        assert stored is not None
        assert len(stored) == 64
        assert tracker.get_original_hash(temp_file) == stored

    def test_get_original_hash_not_found(self, tracker):
        """Test getting hash for file that hasn't been stored."""
        hash_result = tracker.get_original_hash("/unknown/path.txt")
        assert hash_result is None

    def test_content_change_detection(self, tracker, temp_file):
        """Test detection of file content changes."""
        # Store original hash
        original_hash = tracker.calculate_hash(temp_file)
        tracker.store_hash(temp_file, original_hash)

        # File hasn't changed yet
        assert not tracker.has_content_changed(temp_file)

        # Modify file
        with open(temp_file, 'w') as f:
            f.write("Modified content!")

        # Now it should detect the change
        assert tracker.has_content_changed(temp_file)

    def test_content_change_with_no_original(self, tracker, temp_file):
        """Test that no original hash means no change detected."""
        # No original hash stored, so no change detected
        assert not tracker.has_content_changed(temp_file)

    def test_content_change_deleted_file(self, tracker, temp_file):
        """Test detection when file is deleted."""
        tracker.store_hash(temp_file, "abc123")
        os.unlink(temp_file)
        assert tracker.has_content_changed(temp_file)

    def test_get_hash_pair(self, tracker, temp_file):
        """Test getting hash pair (original and current)."""
        original_hash = tracker.calculate_hash(temp_file)
        tracker.store_hash(temp_file, original_hash)

        original, current = tracker.get_hash_pair(temp_file)
        assert original == original_hash
        assert current == original_hash

    def test_multiple_files(self, tracker):
        """Test tracking multiple files."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f1:
            f1.write("File 1")
            file1 = f1.name
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f2:
            f2.write("File 2")
            file2 = f2.name

        try:
            hash1 = tracker.calculate_hash(file1)
            hash2 = tracker.calculate_hash(file2)

            tracker.store_hash(file1, hash1)
            tracker.store_hash(file2, hash2)

            assert hash1 != hash2
            assert tracker.get_original_hash(file1) == hash1
            assert tracker.get_original_hash(file2) == hash2
        finally:
            os.unlink(file1)
            os.unlink(file2)

    def test_large_file_hash(self, tracker):
        """Test hashing a larger file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            # Write 10MB of data
            for i in range(10000):
                f.write("x" * 1024)
            temp_path = f.name

        try:
            hash_result = tracker.calculate_hash(temp_path)
            assert hash_result is not None
            assert len(hash_result) == 64
        finally:
            os.unlink(temp_path)


class TestProcessCapture:
    """Tests for ProcessCapture class."""

    def test_get_current_process_info(self):
        """Test getting current process information."""
        info = ProcessCapture.get_current_process_info()

        assert isinstance(info, dict)
        assert "process_name" in info
        assert "process_id" in info
        assert "process_user" in info
        assert "process_cmdline" in info

        # Should have current PID
        assert info["process_id"] == os.getpid()

    def test_process_info_structure(self):
        """Test that process info has expected structure."""
        info = ProcessCapture.get_current_process_info()

        # Check types
        assert isinstance(info.get("process_name"), str)
        assert isinstance(info.get("process_id"), int) or info.get("process_id") is None
        assert isinstance(info.get("process_user"), str)
        assert isinstance(info.get("process_cmdline"), str)

    def test_format_process_info(self):
        """Test formatting process info."""
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            info = ProcessCapture._format_process_info(proc)

            assert isinstance(info, dict)
            assert "process_name" in info
            assert "process_id" in info
            assert "process_user" in info
            assert "process_cmdline" in info

            # Verify values are reasonable
            assert info["process_id"] == os.getpid()
            assert len(info["process_name"]) > 0
        except ImportError:
            pytest.skip("psutil not available")

    def test_get_system_processes_accessing_path(self):
        """Test getting processes accessing a specific path."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
            f.write(b"test data")

        try:
            processes = ProcessCapture.get_system_processes_accessing_path(temp_path)
            # Result may be empty on restricted systems, but should be a list
            assert isinstance(processes, list)
            for proc in processes:
                assert isinstance(proc, dict)
                assert "process_name" in proc
                assert "process_id" in proc
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    def test_process_capture_error_handling(self):
        """Test that process capture handles errors gracefully."""
        # Try to get process info for non-existent file
        info = ProcessCapture.get_process_by_file_access("/nonexistent/file/path.txt")
        # Should return None or empty dict, not raise exception
        assert info is None or isinstance(info, dict)

    @pytest.mark.skipif(True, reason="Requires admin privileges on Windows")
    def test_get_process_by_file_access(self):
        """Test identifying process by file access."""
        # This test requires admin privileges and specific OS support
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name
            f.write(b"test")

        try:
            # Try to get the process
            info = ProcessCapture.get_process_by_file_access(temp_path)
            # May be None if we can't determine it, but shouldn't crash
            assert info is None or isinstance(info, dict)
        finally:
            os.unlink(temp_path)


class TestMonitorEventEnhanced:
    """Tests for MonitorEvent enhanced monitoring features."""

    def test_monitor_event_basic(self):
        """Test basic MonitorEvent creation."""
        event = MonitorEvent(
            token_id="token-001",
            path="/path/to/file.txt",
            event_type="modified",
            timestamp=time.time(),
            is_directory=False,
            metadata={"test": "data"},
        )

        assert event.token_id == "token-001"
        assert event.path == "/path/to/file.txt"
        assert event.event_type == "modified"
        assert event.is_directory is False
        assert event.process_name is None
        assert event.file_hash_original is None

    def test_monitor_event_with_enhanced_fields(self):
        """Test MonitorEvent with enhanced monitoring fields."""
        event = MonitorEvent(
            token_id="token-001",
            path="/path/to/file.txt",
            event_type="modified",
            timestamp=time.time(),
            is_directory=False,
            metadata={"test": "data"},
            process_name="notepad.exe",
            process_id=1234,
            process_user="DOMAIN\\user",
            process_cmdline="notepad.exe C:\\file.txt",
            file_hash_original="abc123",
            file_hash_current="def456",
            content_modified=True,
        )

        assert event.process_name == "notepad.exe"
        assert event.process_id == 1234
        assert event.process_user == "DOMAIN\\user"
        assert event.process_cmdline == "notepad.exe C:\\file.txt"
        assert event.file_hash_original == "abc123"
        assert event.file_hash_current == "def456"
        assert event.content_modified is True

    def test_monitor_event_to_dict(self):
        """Test converting MonitorEvent to dictionary."""
        event = MonitorEvent(
            token_id="token-001",
            path="/path/to/file.txt",
            event_type="modified",
            timestamp=1234567890,
            is_directory=False,
            metadata={"key": "value"},
            process_name="proc.exe",
            process_id=5678,
            file_hash_original="hash1",
            file_hash_current="hash2",
            content_modified=True,
        )

        event_dict = event.to_dict()

        assert isinstance(event_dict, dict)
        assert event_dict["token_id"] == "token-001"
        assert event_dict["process_name"] == "proc.exe"
        assert event_dict["process_id"] == 5678
        assert event_dict["file_hash_original"] == "hash1"
        assert event_dict["content_modified"] is True

    def test_monitor_event_optional_fields(self):
        """Test that enhanced monitoring fields are optional."""
        event = MonitorEvent(
            token_id="token-001",
            path="/path/to/file.txt",
            event_type="created",
            timestamp=time.time(),
            is_directory=False,
            metadata={},
        )

        # All enhanced monitoring fields should default to None/False
        assert event.process_name is None
        assert event.process_id is None
        assert event.process_user is None
        assert event.process_cmdline is None
        assert event.file_hash_original is None
        assert event.file_hash_current is None
        assert event.content_modified is False


class TestEnhancedMonitoringIntegration:
    """Integration tests for enhanced monitoring features."""

    def test_file_operations_with_hash_tracking(self):
        """Test file operations with hash tracking."""
        tracker = FileHashTracker()

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("Initial content")
            temp_path = f.name

        try:
            # Create event with initial hash
            initial_hash = tracker.calculate_hash(temp_path)
            tracker.store_hash(temp_path, initial_hash)

            event1 = MonitorEvent(
                token_id="token-001",
                path=temp_path,
                event_type="created",
                timestamp=time.time(),
                is_directory=False,
                metadata={},
                file_hash_original=initial_hash,
                file_hash_current=initial_hash,
                content_modified=False,
            )

            assert not event1.content_modified

            # Modify file
            with open(temp_path, 'w') as f:
                f.write("Modified content")

            # Create event with modified hash
            modified_hash = tracker.calculate_hash(temp_path)
            content_changed = tracker.has_content_changed(temp_path)

            event2 = MonitorEvent(
                token_id="token-001",
                path=temp_path,
                event_type="modified",
                timestamp=time.time(),
                is_directory=False,
                metadata={},
                file_hash_original=initial_hash,
                file_hash_current=modified_hash,
                content_modified=content_changed,
            )

            assert event2.content_modified
            assert event1.file_hash_original != event2.file_hash_current

        finally:
            os.unlink(temp_path)

    def test_event_serialization_with_enhanced_data(self):
        """Test that events with enhanced monitoring data can be serialized."""
        import json

        event = MonitorEvent(
            token_id="token-001",
            path="/path/to/file.txt",
            event_type="modified",
            timestamp=1234567890,
            is_directory=False,
            metadata={"extra": "data"},
            process_name="app.exe",
            process_id=9999,
            process_user="user",
            process_cmdline="app.exe --file",
            file_hash_original="abc123",
            file_hash_current="def456",
            content_modified=True,
        )

        # Convert to dict and serialize to JSON
        event_dict = event.to_dict()
        json_str = json.dumps(event_dict)

        # Deserialize back
        deserialized = json.loads(json_str)

        assert deserialized["token_id"] == "token-001"
        assert deserialized["process_name"] == "app.exe"
        assert deserialized["file_hash_original"] == "abc123"
        assert deserialized["content_modified"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
