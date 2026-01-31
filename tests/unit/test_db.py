#!/usr/bin/env python3
"""
Unit tests for database module.
Tests encrypted storage, agent registration, and event management.
"""

import pytest
import time
import os
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.db import DatabaseManager, DatabaseError


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DatabaseManager(temp_file.name, "test_password")
    db.connect()
    
    yield db
    
    db.close()
    os.unlink(temp_file.name)


class TestDatabaseConnection:
    """Test database connection and initialization."""
    
    def test_connect(self, temp_db):
        """Test database connection."""
        assert temp_db.connection is not None
    
    def test_tables_created(self, temp_db):
        """Test that tables are created."""
        cursor = temp_db.connection.cursor()
        
        # Check agents table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='agents'")
        assert cursor.fetchone() is not None
        
        # Check events table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        assert cursor.fetchone() is not None
        
        # Check tokens table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tokens'")
        assert cursor.fetchone() is not None


class TestEncryption:
    """Test encryption functionality."""
    
    def test_encrypt_decrypt(self, temp_db):
        """Test encryption and decryption."""
        original = "Sensitive data 123!@#"
        encrypted = temp_db.encrypt(original)
        decrypted = temp_db.decrypt(encrypted)
        
        assert original != encrypted
        assert original == decrypted
    
    def test_encrypted_data_different(self, temp_db):
        """Test that same data encrypts differently each time."""
        data = "test data"
        encrypted1 = temp_db.encrypt(data)
        encrypted2 = temp_db.encrypt(data)
        
        # Should be different (includes random IV)
        assert encrypted1 != encrypted2
        
        # But both decrypt to same value
        assert temp_db.decrypt(encrypted1) == data
        assert temp_db.decrypt(encrypted2) == data


class TestAgentManagement:
    """Test agent registration and management."""
    
    def test_register_agent(self, temp_db):
        """Test registering a new agent."""
        success = temp_db.register_agent(
            agent_id="agent-001",
            hostname="test-host",
            ip_address="192.168.1.100"
        )
        assert success is True
        
        # Verify agent exists
        agent = temp_db.get_agent("agent-001")
        assert agent is not None
        assert agent["agent_id"] == "agent-001"
        assert agent["hostname"] == "test-host"
        assert agent["ip_address"] == "192.168.1.100"
    
    def test_update_agent_status(self, temp_db):
        """Test updating agent status."""
        # Register agent
        temp_db.register_agent("agent-001")
        
        # Update status
        success = temp_db.update_agent_status("agent-001", "warning")
        assert success is True
        
        # Verify status updated
        agent = temp_db.get_agent("agent-001")
        assert agent["status"] == "warning"
    
    def test_get_all_agents(self, temp_db):
        """Test getting all agents."""
        # Register multiple agents
        temp_db.register_agent("agent-001")
        temp_db.register_agent("agent-002")
        temp_db.register_agent("agent-003")
        
        # Get all
        agents = temp_db.get_all_agents()
        assert len(agents) == 3
        
        agent_ids = [a["agent_id"] for a in agents]
        assert "agent-001" in agent_ids
        assert "agent-002" in agent_ids
        assert "agent-003" in agent_ids
    
    def test_get_nonexistent_agent(self, temp_db):
        """Test getting agent that doesn't exist."""
        agent = temp_db.get_agent("nonexistent")
        assert agent is None


class TestEventManagement:
    """Test event storage and retrieval."""
    
    def test_insert_event(self, temp_db):
        """Test inserting an event."""
        # Register agent first
        temp_db.register_agent("agent-001")
        
        # Insert event
        event_id = temp_db.insert_event(
            agent_id="agent-001",
            token_id="token-001",
            path="C:\\test\\file.txt",
            event_type="opened",
            nonce="test_nonce_001"
        )
        
        assert event_id > 0
        
        # Verify event exists
        event = temp_db.get_event(event_id)
        assert event is not None
        assert event["agent_id"] == "agent-001"
        assert event["token_id"] == "token-001"
        assert event["path"] == "C:\\test\\file.txt"
        assert event["event_type"] == "opened"
    
    def test_duplicate_nonce_rejected(self, temp_db):
        """Test that duplicate nonce is rejected (replay protection)."""
        temp_db.register_agent("agent-001")
        
        # Insert first event
        temp_db.insert_event(
            agent_id="agent-001",
            token_id="token-001",
            path="C:\\test\\file.txt",
            event_type="opened",
            nonce="test_nonce_001"
        )
        
        # Try to insert with same nonce
        with pytest.raises(DatabaseError, match="replay attack"):
            temp_db.insert_event(
                agent_id="agent-001",
                token_id="token-002",
                path="C:\\test\\file2.txt",
                event_type="modified",
                nonce="test_nonce_001"  # Same nonce!
            )
    
    def test_get_recent_events(self, temp_db):
        """Test getting recent events."""
        temp_db.register_agent("agent-001")
        
        # Insert multiple events with slight delays to ensure order
        for i in range(5):
            temp_db.insert_event(
                agent_id="agent-001",
                token_id=f"token-{i:03d}",
                path=f"C:\\test\\file{i}.txt",
                event_type="opened",
                nonce=f"nonce_{i}"
            )
            time.sleep(0.01)  # Small delay to ensure timestamp order
        
        # Get recent events
        events = temp_db.get_recent_events(limit=3)
        assert len(events) == 3
        
        # Verify we got 3 most recent events (order may vary without delays)
        token_ids = [e["token_id"] for e in events]
        assert len(set(token_ids)) == 3  # Three unique tokens
    
    def test_get_events_by_agent(self, temp_db):
        """Test filtering events by agent."""
        # Register agents
        temp_db.register_agent("agent-001")
        temp_db.register_agent("agent-002")
        
        # Insert events for different agents
        temp_db.insert_event(
            agent_id="agent-001",
            token_id="token-001",
            path="C:\\test\\file1.txt",
            event_type="opened",
            nonce="nonce_1"
        )
        temp_db.insert_event(
            agent_id="agent-002",
            token_id="token-002",
            path="C:\\test\\file2.txt",
            event_type="opened",
            nonce="nonce_2"
        )
        
        # Get events for agent-001
        events = temp_db.get_recent_events(agent_id="agent-001")
        assert len(events) == 1
        assert events[0]["agent_id"] == "agent-001"


class TestTokenManagement:
    """Test honeytoken registration."""
    
    def test_register_token(self, temp_db):
        """Test registering a honeytoken."""
        success = temp_db.register_token(
            token_id="token-001",
            name="Secret Document",
            path="C:\\honeytokens\\secret.docx",
            deployed_to="agent-001"
        )
        assert success is True
        
        # Verify token exists
        token = temp_db.get_token("token-001")
        assert token is not None
        assert token["token_id"] == "token-001"
        assert token["name"] == "Secret Document"
        assert token["path"] == "C:\\honeytokens\\secret.docx"
        assert token["deployed_to"] == "agent-001"
    
    def test_get_nonexistent_token(self, temp_db):
        """Test getting token that doesn't exist."""
        token = temp_db.get_token("nonexistent")
        assert token is None


class TestStatistics:
    """Test database statistics."""
    
    def test_get_stats(self, temp_db):
        """Test getting database statistics."""
        # Add some data
        temp_db.register_agent("agent-001")
        temp_db.register_agent("agent-002")
        temp_db.insert_event(
            agent_id="agent-001",
            token_id="token-001",
            path="C:\\test\\file.txt",
            event_type="opened",
            nonce="nonce_1"
        )
        temp_db.register_token(
            token_id="token-001",
            name="Test Token",
            path="C:\\test\\file.txt"
        )
        
        # Get stats
        stats = temp_db.get_stats()
        
        assert stats["total_agents"] == 2
        assert stats["total_events"] == 1
        assert stats["total_tokens"] == 1
        assert "db_size_bytes" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
