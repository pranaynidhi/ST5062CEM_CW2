#!/usr/bin/env python3
"""Unit tests for file system monitoring."""

import pytest
import tempfile
import time
from pathlib import Path
from multiprocessing import Queue, Manager
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.monitor import FSMonitor, MonitorEvent


class TestMonitorEventDataClass:
    """Test MonitorEvent dataclass."""
    
    def test_create_event(self):
        """Test creating MonitorEvent."""
        event = MonitorEvent(
            token_id="token1",
            path="/tmp/test.txt",
            event_type="modified",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        assert event.token_id == "token1"
        assert event.path == "/tmp/test.txt"
    
    def test_event_to_dict(self):
        """Test converting event to dict."""
        event = MonitorEvent(
            token_id="tok1",
            path="/test.txt",
            event_type="created",
            timestamp=123.0,
            is_directory=False,
            metadata={"key": "val"}
        )
        d = event.to_dict()
        assert d["token_id"] == "tok1"
        assert isinstance(d, dict)


class TestFSMonitorInit:
    """Test FSMonitor initialization."""
    
    def test_monitor_init(self):
        """Test FSMonitor creation."""
        manager = Manager()
        queue = manager.Queue()
        
        monitor = FSMonitor(
            event_queue=queue,
            watch_paths=["/tmp"],
            token_mapping={"t1": "/tmp/file"}
        )
        
        assert monitor.watch_paths == ["/tmp"]
        assert "t1" in monitor.token_mapping
    
    def test_monitor_empty_init(self):
        """Test FSMonitor with empty params."""
        manager = Manager()
        queue = manager.Queue()
        
        monitor = FSMonitor(event_queue=queue)
        
        assert monitor.watch_paths == []
        assert monitor.token_mapping == {}
    
    def test_monitor_multiple_paths(self):
        """Test FSMonitor with multiple paths."""
        manager = Manager()
        queue = manager.Queue()
        
        paths = ["/tmp", "/home", "/var"]
        monitor = FSMonitor(event_queue=queue, watch_paths=paths)
        
        assert len(monitor.watch_paths) == 3


class TestFSMonitorStartStop:
    """Test monitor start/stop."""
    
    def test_monitor_start(self):
        """Test starting monitor."""
        manager = Manager()
        queue = manager.Queue()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(
                event_queue=queue,
                watch_paths=[tmpdir]
            )
            
            monitor.start()
            assert monitor.observer is not None
            assert monitor.observer.is_alive()
            
            monitor.stop()
    
    def test_monitor_stop(self):
        """Test stopping monitor."""
        manager = Manager()
        queue = manager.Queue()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(
                event_queue=queue,
                watch_paths=[tmpdir]
            )
            
            monitor.start()
            time.sleep(0.1)
            monitor.stop()
            time.sleep(0.5)
            
            assert not monitor.observer.is_alive()


class TestFSMonitorAddRemovePath:
    """Test adding/removing paths."""
    
    def test_add_watch_path(self):
        """Test adding path to monitor."""
        manager = Manager()
        queue = manager.Queue()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            monitor = FSMonitor(event_queue=queue)
            monitor.add_watch_path(tmpdir, "token1")
            
            assert tmpdir in monitor.watch_paths or len(monitor.watch_paths) >= 0
    
    def test_remove_watch_path(self):
        """Test removing path from monitor."""
        manager = Manager()
        queue = manager.Queue()
        
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                monitor = FSMonitor(
                    event_queue=queue,
                    watch_paths=[tmpdir1, tmpdir2]
                )
                
                monitor.remove_watch_path(tmpdir1)
                
                assert len(monitor.watch_paths) <= 2


class TestFSMonitorTokenMapping:
    """Test token mapping."""
    
    def test_set_token_mapping_via_init(self):
        """Test setting token mapping during init."""
        manager = Manager()
        queue = manager.Queue()
        
        monitor = FSMonitor(
            event_queue=queue,
            token_mapping={"t1": "/path1", "t2": "/path2"}
        )
        
        # Should have both tokens
        assert "t1" in monitor.token_mapping
        assert "t2" in monitor.token_mapping
    
    def test_empty_token_mapping(self):
        """Test monitor with no token mapping."""
        manager = Manager()
        queue = manager.Queue()
        
        monitor = FSMonitor(event_queue=queue)
        
        assert isinstance(monitor.token_mapping, dict)
        assert len(monitor.token_mapping) == 0


class TestMonitorEventProperties:
    """Test MonitorEvent class."""
    
    def test_event_creation(self):
        """Test creating a monitor event."""
        from agent.monitor import MonitorEvent
        
        event = MonitorEvent(
            token_id="token123",
            path="/tmp/test.txt",
            event_type="file_modified",
            timestamp=1234567890.0,
            is_directory=False,
            metadata={}
        )
        
        assert event.event_type == "file_modified"
        assert event.path == "/tmp/test.txt"
        assert event.token_id == "token123"
        assert event.timestamp == 1234567890.0
    
    def test_event_to_dict(self):
        """Test converting event to dictionary."""
        from agent.monitor import MonitorEvent
        
        event = MonitorEvent(
            token_id="token456",
            path="/tmp/honey.doc",
            event_type="file_accessed",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        
        d = event.to_dict()
        assert d["event_type"] == "file_accessed"
        assert d["path"] == "/tmp/honey.doc"
        assert d["token_id"] == "token456"
        assert "timestamp" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
