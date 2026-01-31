#!/usr/bin/env python3
"""
Unit tests for protocol module.
Tests message creation, framing, parsing, and validation.
"""

import pytest
import time
import json
import struct
import base64
import secrets
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.protocol import (
    Message,
    MessageHeader,
    generate_nonce,
    create_message,
    create_event_message,
    create_heartbeat_message,
    frame_message,
    parse_message,
    ValidationError,
    FramingError,
    MessageTooLargeError,
    NONCE_SIZE
)


class TestNonceGeneration:
    """Test nonce generation."""
    
    def test_nonce_length(self):
        """Test that nonce is correct length."""
        nonce = generate_nonce()
        decoded = base64.b64decode(nonce)
        assert len(decoded) == NONCE_SIZE
    
    def test_nonce_uniqueness(self):
        """Test that nonces are unique."""
        nonces = [generate_nonce() for _ in range(100)]
        assert len(set(nonces)) == 100
    
    def test_nonce_is_base64(self):
        """Test that nonce is valid base64."""
        nonce = generate_nonce()
        # Should not raise exception
        decoded = base64.b64decode(nonce)
        assert decoded is not None


class TestMessageHeader:
    """Test MessageHeader class."""
    
    def test_create_header(self):
        """Test creating a message header."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent-001",
            msg_type="event"
        )
        assert header.agent_id == "agent-001"
        assert header.msg_type == "event"
    
    def test_header_to_dict(self):
        """Test converting header to dict."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent-001",
            msg_type="event"
        )
        d = header.to_dict()
        assert "nonce" in d
        assert "timestamp" in d
        assert "agent_id" in d
        assert "msg_type" in d
    
    def test_header_from_dict(self):
        """Test creating header from dict."""
        data = {
            "nonce": generate_nonce(),
            "timestamp": int(time.time()),
            "agent_id": "agent-001",
            "msg_type": "event"
        }
        header = MessageHeader.from_dict(data)
        assert header.agent_id == "agent-001"
        assert header.msg_type == "event"
    
    def test_header_validation_valid(self):
        """Test validating a valid header."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent-001",
            msg_type="event"
        )
        # Should not raise exception
        header.validate()
    
    def test_header_validation_invalid_nonce(self):
        """Test validation fails with invalid nonce."""
        header = MessageHeader(
            nonce="invalid_nonce",
            timestamp=int(time.time()),
            agent_id="agent-001",
            msg_type="event"
        )
        with pytest.raises(ValidationError):
            header.validate()
    
    def test_header_validation_invalid_timestamp(self):
        """Test validation fails with old timestamp."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()) - 120,  # 2 minutes ago
            agent_id="agent-001",
            msg_type="event"
        )
        with pytest.raises(ValidationError):
            header.validate()
    
    def test_header_validation_invalid_msg_type(self):
        """Test validation fails with invalid message type."""
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()),
            agent_id="agent-001",
            msg_type="invalid_type"
        )
        with pytest.raises(ValidationError):
            header.validate()


class TestMessage:
    """Test Message class."""
    
    def test_create_message(self):
        """Test creating a message."""
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={"test": "data"}
        )
        assert msg.header.agent_id == "agent-001"
        assert msg.header.msg_type == "event"
        assert msg.data == {"test": "data"}
    
    def test_create_event_message(self):
        """Test creating an event message."""
        msg = create_event_message(
            agent_id="agent-001",
            token_id="token-001",
            path="C:\\test\\file.txt",
            event_type="opened"
        )
        assert msg.header.msg_type == "event"
        assert msg.data["token_id"] == "token-001"
        assert msg.data["path"] == "C:\\test\\file.txt"
        assert msg.data["event_type"] == "opened"
    
    def test_create_heartbeat_message(self):
        """Test creating a heartbeat message."""
        msg = create_heartbeat_message(
            agent_id="agent-001",
            status="healthy"
        )
        assert msg.header.msg_type == "heartbeat"
        assert msg.data["status"] == "healthy"
    
    def test_message_to_dict(self):
        """Test converting message to dict."""
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={"test": "data"}
        )
        d = msg.to_dict()
        assert "header" in d
        assert "data" in d
    
    def test_message_from_dict(self):
        """Test creating message from dict."""
        original = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={"test": "data"}
        )
        d = original.to_dict()
        msg = Message.from_dict(d)
        assert msg.header.agent_id == "agent-001"
        assert msg.data == {"test": "data"}


class TestFraming:
    """Test message framing."""
    
    def test_frame_message(self):
        """Test framing a message."""
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={"test": "data"}
        )
        framed = frame_message(msg)
        
        # Check length prefix
        length = struct.unpack('!I', framed[:4])[0]
        assert length == len(framed) - 4
    
    def test_frame_parse_roundtrip(self):
        """Test framing and parsing roundtrip."""
        original = create_event_message(
            agent_id="agent-001",
            token_id="token-001",
            path="C:\\test\\file.txt",
            event_type="opened"
        )
        
        # Frame
        framed = frame_message(original)
        
        # Extract payload
        payload = framed[4:]
        
        # Parse
        parsed = parse_message(payload)
        
        # Verify
        assert parsed.header.agent_id == original.header.agent_id
        assert parsed.data["token_id"] == original.data["token_id"]
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON fails."""
        invalid_json = b"not valid json"
        with pytest.raises(ValidationError):
            parse_message(invalid_json)
    
    def test_parse_missing_header(self):
        """Test parsing message without header fails."""
        invalid_msg = json.dumps({"data": {}}).encode('utf-8')
        with pytest.raises(ValidationError):
            parse_message(invalid_msg)
    
    def test_parse_missing_data(self):
        """Test parsing message without data fails."""
        invalid_msg = json.dumps({"header": {}}).encode('utf-8')
        with pytest.raises(ValidationError):
            parse_message(invalid_msg)


class TestValidation:
    """Test message validation."""
    
    def test_valid_message(self):
        """Test that valid message passes validation."""
        msg = create_message(
            agent_id="agent-001",
            msg_type="event",
            data={"test": "data"}
        )
        # Should not raise
        msg.validate()
    
    def test_invalid_nonce_size(self):
        """Test that wrong nonce size fails validation."""
        # Create message with invalid nonce
        header = MessageHeader(
            nonce=base64.b64encode(b"short").decode(),
            timestamp=int(time.time()),
            agent_id="agent-001",
            msg_type="event"
        )
        msg = Message(header=header, data={})
        
        with pytest.raises(ValidationError):
            msg.validate()
    
    def test_timestamp_tolerance(self):
        """Test timestamp validation tolerance."""
        # 50 seconds ago (within tolerance)
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()) - 50,
            agent_id="agent-001",
            msg_type="event"
        )
        msg = Message(header=header, data={})
        # Should not raise
        msg.validate()
        
        # 70 seconds ago (outside tolerance)
        header = MessageHeader(
            nonce=generate_nonce(),
            timestamp=int(time.time()) - 70,
            agent_id="agent-001",
            msg_type="event"
        )
        msg = Message(header=header, data={})
        with pytest.raises(ValidationError):
            msg.validate()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
