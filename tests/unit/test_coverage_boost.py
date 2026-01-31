#!/usr/bin/env python3
"""
Comprehensive tests to boost coverage.
"""

import pytest
import time
import tempfile
import os
from pathlib import Path
from multiprocessing import Manager
import sys
import json

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.sender import RateLimiter
from agent.monitor import MonitorEvent, FSMonitor
from server.protocol import Message, MessageHeader, generate_nonce, ValidationError
from server.db import DatabaseManager


class TestRateLimiterComprehensive:
    """Comprehensive rate limiter tests."""
    
    def test_limiter_starts_full(self):
        """Test limiter starts with full burst."""
        limiter = RateLimiter(rate=5.0, burst=10)
        assert limiter.tokens == 10.0
    
    def test_limiter_rate_stored(self):
        """Test limiter stores rate correctly."""
        limiter = RateLimiter(rate=25.5, burst=100)
        assert limiter.rate == 25.5
    
    def test_limiter_burst_stored(self):
        """Test limiter stores burst correctly."""
        limiter = RateLimiter(rate=10.0, burst=50)
        assert limiter.burst == 50
    
    def test_limiter_has_lock(self):
        """Test limiter has threading lock."""
        limiter = RateLimiter()
        assert limiter.lock is not None
    
    def test_limiter_last_refill_initialized(self):
        """Test last_refill is initialized."""
        before = time.time()
        limiter = RateLimiter()
        after = time.time()
        assert before <= limiter.last_refill <= after


class TestMonitorEventComprehensive:
    """Comprehensive MonitorEvent tests."""
    
    def test_event_token_id_stored(self):
        """Test token_id is stored correctly."""
        event = MonitorEvent(
            token_id="my-token",
            path="/path",
            event_type="opened",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        assert event.token_id == "my-token"
    
    def test_event_path_stored(self):
        """Test path is stored correctly."""
        event = MonitorEvent(
            token_id="token",
            path="/var/honey/file.txt",
            event_type="opened",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        assert event.path == "/var/honey/file.txt"
    
    def test_event_type_stored(self):
        """Test event_type is stored correctly."""
        event = MonitorEvent(
            token_id="token",
            path="/path",
            event_type="modified",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        assert event.event_type == "modified"
    
    def test_event_timestamp_stored(self):
        """Test timestamp is stored correctly."""
        ts = 1234567890.123
        event = MonitorEvent(
            token_id="token",
            path="/path",
            event_type="opened",
            timestamp=ts,
            is_directory=False,
            metadata={}
        )
        assert event.timestamp == ts
    
    def test_event_is_directory_false(self):
        """Test is_directory=False is stored."""
        event = MonitorEvent(
            token_id="token",
            path="/path/file.txt",
            event_type="opened",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        assert event.is_directory is False
    
    def test_event_is_directory_true(self):
        """Test is_directory=True is stored."""
        event = MonitorEvent(
            token_id="token",
            path="/path/dir",
            event_type="created",
            timestamp=time.time(),
            is_directory=True,
            metadata={}
        )
        assert event.is_directory is True
    
    def test_event_metadata_empty(self):
        """Test empty metadata."""
        event = MonitorEvent(
            token_id="token",
            path="/path",
            event_type="opened",
            timestamp=time.time(),
            is_directory=False,
            metadata={}
        )
        assert event.metadata == {}
    
    def test_event_metadata_with_data(self):
        """Test metadata with data."""
        metadata = {"key": "value", "number": 42}
        event = MonitorEvent(
            token_id="token",
            path="/path",
            event_type="opened",
            timestamp=time.time(),
            is_directory=False,
            metadata=metadata
        )
        assert event.metadata["key"] == "value"
        assert event.metadata["number"] == 42


class TestFSMonitorComprehensive:
    """Comprehensive FSMonitor tests."""
    
    def test_monitor_event_queue_stored(self):
        """Test event queue is stored."""
        manager = Manager()
        queue = manager.Queue()
        monitor = FSMonitor(event_queue=queue)
        assert monitor.event_queue is queue
    
    def test_monitor_watch_paths_list(self):
        """Test watch_paths is a list."""
        manager = Manager()
        queue = manager.Queue()
        monitor = FSMonitor(event_queue=queue, watch_paths=[])
        assert isinstance(monitor.watch_paths, list)
    
    def test_monitor_token_mapping_dict(self):
        """Test token_mapping is a dict."""
        manager = Manager()
        queue = manager.Queue()
        monitor = FSMonitor(event_queue=queue)
        assert isinstance(monitor.token_mapping, dict)
    
    def test_monitor_observer_initially_none(self):
        """Test observer is None initially."""
        manager = Manager()
        queue = manager.Queue()
        monitor = FSMonitor(event_queue=queue)
        assert monitor.observer is None


class TestMessageHeaderComprehensive:
    """Comprehensive MessageHeader tests."""
    
    def test_header_has_nonce(self):
        """Test header has nonce."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent",
            msg_type="event"
        )
        assert header.nonce is not None
    
    def test_header_has_timestamp(self):
        """Test header has timestamp."""
        ts = int(time.time())
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=ts,
            agent_id="agent",
            msg_type="event"
        )
        assert header.timestamp == ts
    
    def test_header_has_agent_id(self):
        """Test header has agent_id."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="my-agent",
            msg_type="event"
        )
        assert header.agent_id == "my-agent"
    
    def test_header_has_msg_type(self):
        """Test header has msg_type."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent",
            msg_type="heartbeat"
        )
        assert header.msg_type == "heartbeat"


class TestMessageComprehensive:
    """Comprehensive Message tests."""
    
    def test_message_has_header(self):
        """Test message has header."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent",
            msg_type="event"
        )
        msg = Message(header=header, data={})
        assert msg.header is header
    
    def test_message_has_data(self):
        """Test message has data."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent",
            msg_type="event"
        )
        data = {"key": "value"}
        msg = Message(header=header, data=data)
        assert msg.data == data
    
    def test_message_to_dict_has_header(self):
        """Test message to_dict includes header."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent",
            msg_type="event"
        )
        msg = Message(header=header, data={})
        d = msg.to_dict()
        assert "header" in d
    
    def test_message_to_dict_has_data(self):
        """Test message to_dict includes data."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent",
            msg_type="event"
        )
        msg = Message(header=header, data={})
        d = msg.to_dict()
        assert "data" in d


@pytest.fixture
def temp_db():
    """Create temporary database."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DatabaseManager(temp_file.name, "test_pass")
    db.connect()
    
    yield db
    
    db.close()
    os.unlink(temp_file.name)


class TestDatabaseComprehensive:
    """Comprehensive database tests."""
    
    def test_db_has_connection(self, temp_db):
        """Test database has connection."""
        assert temp_db.connection is not None
    
    def test_encrypt_returns_string(self, temp_db):
        """Test encrypt returns string (base64)."""
        encrypted = temp_db.encrypt("test")
        assert isinstance(encrypted, str)
    
    def test_decrypt_returns_string(self, temp_db):
        """Test decrypt returns string."""
        encrypted = temp_db.encrypt("test")
        decrypted = temp_db.decrypt(encrypted)
        assert isinstance(decrypted, str)
    
    def test_register_agent_returns_bool(self, temp_db):
        """Test register_agent returns boolean."""
        result = temp_db.register_agent("agent-001")
        assert isinstance(result, bool)
    
    def test_register_token_returns_bool(self, temp_db):
        """Test register_token returns boolean."""
        result = temp_db.register_token("token-001", "Token", "/path")
        assert isinstance(result, bool)
    
    def test_insert_event_returns_int(self, temp_db):
        """Test insert_event returns int (row ID)."""
        temp_db.register_agent("agent-001")
        result = temp_db.insert_event("agent-001", "token", "/path", "opened", "nonce")
        assert isinstance(result, int)
    
    def test_get_agent_with_nonexistent_returns_none(self, temp_db):
        """Test get_agent with nonexistent agent returns None."""
        agent = temp_db.get_agent("nonexistent")
        assert agent is None
    
    def test_get_token_with_nonexistent_returns_none(self, temp_db):
        """Test get_token with nonexistent token returns None."""
        token = temp_db.get_token("nonexistent")
        assert token is None
    
    def test_stats_returns_dict(self, temp_db):
        """Test get_stats returns dict."""
        stats = temp_db.get_stats()
        assert isinstance(stats, dict)
    
    def test_stats_has_total_agents(self, temp_db):
        """Test stats has total_agents."""
        stats = temp_db.get_stats()
        assert "total_agents" in stats
    
    def test_stats_has_total_events(self, temp_db):
        """Test stats has total_events."""
        stats = temp_db.get_stats()
        assert "total_events" in stats
    
    def test_stats_has_total_tokens(self, temp_db):
        """Test stats has total_tokens."""
        stats = temp_db.get_stats()
        assert "total_tokens" in stats
    
    def test_get_events_by_timerange_returns_list(self, temp_db):
        """Test get_events_by_timerange returns list."""
        events = temp_db.get_events_by_timerange(0, int(time.time()) + 100)
        assert isinstance(events, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
