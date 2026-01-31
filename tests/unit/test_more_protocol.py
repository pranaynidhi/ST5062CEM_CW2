#!/usr/bin/env python3
"""
More comprehensive tests for existing functionality.
"""

import pytest
import time
from pathlib import Path
import sys
import base64

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.protocol import (
    Message,
    MessageHeader,
    create_message,
    create_heartbeat_message,
    generate_nonce,
    NONCE_SIZE
)


class TestMessageCreation:
    """Test message creation functions."""
    
    def test_create_message_status(self):
        """Test creating status message."""
        msg = create_message(
            agent_id="agent-001",
            msg_type="status",
            data={"status": "active", "uptime": 3600}
        )
        
        assert msg.header.msg_type == "status"
        assert msg.header.agent_id == "agent-001"
        assert msg.data["status"] == "active"
    
    def test_create_heartbeat_basic(self):
        """Test creating basic heartbeat message."""
        msg = create_heartbeat_message(
            agent_id="agent-001",
            status="active"
        )
        
        assert msg.header.msg_type == "heartbeat"
        assert msg.data["status"] == "active"
    
    def test_nonce_generation_unique(self):
        """Test that consecutive nonces are different."""
        nonce1 = generate_nonce()
        nonce2 = generate_nonce()
        nonce3 = generate_nonce()
        
        assert nonce1 != nonce2
        assert nonce2 != nonce3
        assert nonce1 != nonce3
    
    def test_message_header_nonce_valid(self):
        """Test that message headers have valid nonces."""
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={}
        )
        
        nonce_bytes = base64.b64decode(msg.header.nonce)
        assert len(nonce_bytes) == NONCE_SIZE
    
    def test_message_timestamp_current(self):
        """Test that message timestamps are current."""
        before = int(time.time())
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={}
        )
        after = int(time.time())
        
        assert before <= msg.header.timestamp <= after + 1
    
    def test_create_multiple_messages(self):
        """Test creating multiple messages."""
        messages = []
        for i in range(10):
            msg = create_message(
                agent_id=f"agent-{i:03d}",
                msg_type="event",
                data={"index": i}
            )
            messages.append(msg)
        
        assert len(messages) == 10
        # All should have unique nonces
        nonces = [m.header.nonce for m in messages]
        assert len(set(nonces)) == 10


class TestMessageHeaderProperties:
    """Test MessageHeader properties."""
    
    def test_header_agent_id_types(self):
        """Test headers with various agent ID formats."""
        agent_ids = ["agent-001", "client_123", "honeypot-server-01", "AGT_XYZ"]
        
        for agent_id in agent_ids:
            header = MessageHeader(
                nonce=generate_nonce(),
                timestamp=int(time.time()),
                agent_id=agent_id,
                msg_type="event"
            )
            
            assert header.agent_id == agent_id
    
    def test_header_message_types(self):
        """Test headers with different message types."""
        msg_types = ["event", "heartbeat", "status"]
        
        for msg_type in msg_types:
            header = MessageHeader(
                nonce=generate_nonce(),
                timestamp=int(time.time()),
                agent_id="test-agent",
                msg_type=msg_type
            )
            
            assert header.msg_type == msg_type
    
    def test_header_dict_conversion_roundtrip(self):
        """Test converting header to dict and back."""
        original = MessageHeader(
            nonce=generate_nonce(),
            timestamp=1234567890,
            agent_id="agent-001",
            msg_type="event"
        )
        
        # Convert to dict
        d = original.to_dict()
        
        # Convert back
        restored = MessageHeader.from_dict(d)
        
        assert restored.nonce == original.nonce
        assert restored.timestamp == original.timestamp
        assert restored.agent_id == original.agent_id
        assert restored.msg_type == original.msg_type


class TestMessageDataFormats:
    """Test messages with various data formats."""
    
    def test_message_with_nested_data(self):
        """Test message with nested data structures."""
        data = {
            "event": {
                "type": "file_access",
                "file": {
                    "path": "/tmp/honey.txt",
                    "size": 1024
                },
                "user": {
                    "name": "attacker",
                    "id": 1001
                }
            }
        }
        
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data=data
        )
        
        assert msg.data["event"]["file"]["size"] == 1024
    
    def test_message_with_list_data(self):
        """Test message with list in data."""
        data = {
            "watched_files": [
                "/tmp/honey1.txt",
                "/tmp/honey2.doc",
                "/var/secrets/data.pdf"
            ],
            "count": 3
        }
        
        msg = create_message(
            agent_id="agent-001",
            msg_type="status",
            data=data
        )
        
        assert len(msg.data["watched_files"]) == 3
    
    def test_message_with_numeric_data(self):
        """Test message with various numeric types."""
        data = {
            "integer": 42,
            "float": 3.14159,
            "negative": -100,
            "zero": 0
        }
        
        msg = create_message(
            agent_id="agent-001",
            msg_type="status",
            data=data
        )
        
        assert msg.data["integer"] == 42
        assert msg.data["float"] == 3.14159
    
    def test_message_with_boolean_data(self):
        """Test message with boolean values."""
        data = {
            "is_active": True,
            "has_error": False,
            "verbose": True
        }
        
        msg = create_message(
            agent_id="agent-001",
            msg_type="status",
            data=data
        )
        
        assert msg.data["is_active"] is True
        assert msg.data["has_error"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
