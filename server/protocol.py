#!/usr/bin/env python3
"""
HoneyGrid Protocol Module
Handles message framing, parsing, and validation for agent-server communication.

Protocol Format:
    [4-byte length prefix (big-endian)] + [JSON payload]

JSON Payload Structure:
    {
        "header": {
            "nonce": "base64-encoded 12-byte random value",
            "timestamp": 1234567890,  # Unix timestamp (seconds)
            "agent_id": "agent-001",
            "msg_type": "event" | "heartbeat" | "deploy_response"
        },
        "data": {
            // Message-specific data
        }
    }
"""

import json
import struct
import time
import secrets
import base64
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass, asdict


# Protocol Constants
HEADER_LENGTH = 4  # 4 bytes for length prefix
MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB maximum message size
NONCE_SIZE = 12  # 12 bytes for nonce
TIMESTAMP_TOLERANCE = 60  # ±60 seconds tolerance for timestamp validation


class ProtocolError(Exception):
    """Base exception for protocol errors."""
    pass


class FramingError(ProtocolError):
    """Raised when message framing is invalid."""
    pass


class ValidationError(ProtocolError):
    """Raised when message validation fails."""
    pass


class MessageTooLargeError(ProtocolError):
    """Raised when message exceeds maximum size."""
    pass


@dataclass
class MessageHeader:
    """Message header containing metadata."""
    nonce: str  # Base64-encoded nonce
    timestamp: int  # Unix timestamp
    agent_id: str
    msg_type: str  # "event", "heartbeat", "deploy_response"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageHeader':
        """Create from dictionary."""
        return cls(**data)
    
    def validate(self) -> None:
        """Validate header fields."""
        # Validate nonce
        if not self.nonce:
            raise ValidationError("Missing nonce")
        try:
            nonce_bytes = base64.b64decode(self.nonce)
            if len(nonce_bytes) != NONCE_SIZE:
                raise ValidationError(f"Invalid nonce size: {len(nonce_bytes)} (expected {NONCE_SIZE})")
        except Exception as e:
            raise ValidationError(f"Invalid nonce encoding: {e}")
        
        # Validate timestamp
        if not isinstance(self.timestamp, int):
            raise ValidationError("Timestamp must be an integer")
        
        current_time = int(time.time())
        time_diff = abs(current_time - self.timestamp)
        if time_diff > TIMESTAMP_TOLERANCE:
            raise ValidationError(
                f"Timestamp out of tolerance: {time_diff}s (max: {TIMESTAMP_TOLERANCE}s)"
            )
        
        # Validate agent_id
        if not self.agent_id or not isinstance(self.agent_id, str):
            raise ValidationError("Invalid agent_id")
        
        # Validate message type
        valid_types = ["event", "heartbeat", "deploy_response", "status"]
        if self.msg_type not in valid_types:
            raise ValidationError(f"Invalid msg_type: {self.msg_type}")


@dataclass
class Message:
    """Complete protocol message."""
    header: MessageHeader
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "header": self.header.to_dict(),
            "data": self.data
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create from dictionary."""
        return cls(
            header=MessageHeader.from_dict(data["header"]),
            data=data["data"]
        )
    
    def validate(self) -> None:
        """Validate message."""
        self.header.validate()
        if not isinstance(self.data, dict):
            raise ValidationError("Data must be a dictionary")


def generate_nonce() -> str:
    """
    Generate a cryptographically secure random nonce.
    
    Returns:
        Base64-encoded 12-byte nonce
    """
    nonce_bytes = secrets.token_bytes(NONCE_SIZE)
    return base64.b64encode(nonce_bytes).decode('ascii')


def create_message(
    agent_id: str,
    msg_type: str,
    data: Dict[str, Any],
    timestamp: Optional[int] = None
) -> Message:
    """
    Create a new protocol message.
    
    Args:
        agent_id: Agent identifier
        msg_type: Message type ("event", "heartbeat", etc.)
        data: Message payload data
        timestamp: Unix timestamp (defaults to current time)
    
    Returns:
        Message object
    """
    if timestamp is None:
        timestamp = int(time.time())
    
    header = MessageHeader(
        nonce=generate_nonce(),
        timestamp=timestamp,
        agent_id=agent_id,
        msg_type=msg_type
    )
    
    message = Message(header=header, data=data)
    message.validate()
    return message


def frame_message(message: Message) -> bytes:
    """
    Frame a message for transmission.
    
    Args:
        message: Message to frame
    
    Returns:
        Framed bytes: [4-byte length][JSON payload]
    
    Raises:
        MessageTooLargeError: If message exceeds maximum size
    """
    # Serialize to JSON
    json_data = json.dumps(message.to_dict()).encode('utf-8')
    
    # Check size
    if len(json_data) > MAX_MESSAGE_SIZE:
        raise MessageTooLargeError(
            f"Message size {len(json_data)} exceeds maximum {MAX_MESSAGE_SIZE}"
        )
    
    # Create length prefix (4 bytes, big-endian)
    length_prefix = struct.pack('!I', len(json_data))
    
    return length_prefix + json_data


async def read_frame(reader) -> bytes:
    """
    Read a framed message from an asyncio StreamReader.
    
    Args:
        reader: asyncio.StreamReader
    
    Returns:
        Message payload bytes (without length prefix)
    
    Raises:
        FramingError: If frame is invalid
        MessageTooLargeError: If message exceeds maximum size
        EOFError: If connection closed
    """
    # Read length prefix
    length_data = await reader.readexactly(HEADER_LENGTH)
    if len(length_data) < HEADER_LENGTH:
        raise EOFError("Connection closed")
    
    # Unpack length
    message_length = struct.unpack('!I', length_data)[0]
    
    # Validate length
    if message_length == 0:
        raise FramingError("Invalid message length: 0")
    if message_length > MAX_MESSAGE_SIZE:
        raise MessageTooLargeError(
            f"Message size {message_length} exceeds maximum {MAX_MESSAGE_SIZE}"
        )
    
    # Read payload
    payload = await reader.readexactly(message_length)
    if len(payload) < message_length:
        raise FramingError(f"Incomplete message: expected {message_length}, got {len(payload)}")
    
    return payload


def read_frame_sync(sock) -> bytes:
    """
    Read a framed message from a socket (synchronous).
    
    Args:
        sock: socket.socket
    
    Returns:
        Message payload bytes (without length prefix)
    
    Raises:
        FramingError: If frame is invalid
        MessageTooLargeError: If message exceeds maximum size
        EOFError: If connection closed
    """
    # Read length prefix
    length_data = _recv_exact(sock, HEADER_LENGTH)
    if len(length_data) < HEADER_LENGTH:
        raise EOFError("Connection closed")
    
    # Unpack length
    message_length = struct.unpack('!I', length_data)[0]
    
    # Validate length
    if message_length == 0:
        raise FramingError("Invalid message length: 0")
    if message_length > MAX_MESSAGE_SIZE:
        raise MessageTooLargeError(
            f"Message size {message_length} exceeds maximum {MAX_MESSAGE_SIZE}"
        )
    
    # Read payload
    payload = _recv_exact(sock, message_length)
    if len(payload) < message_length:
        raise FramingError(f"Incomplete message: expected {message_length}, got {len(payload)}")
    
    return payload


def _recv_exact(sock, num_bytes: int) -> bytes:
    """
    Receive exact number of bytes from socket.
    
    Args:
        sock: socket.socket
        num_bytes: Number of bytes to receive
    
    Returns:
        Received bytes
    
    Raises:
        EOFError: If connection closed before receiving all bytes
    """
    chunks = []
    bytes_received = 0
    
    while bytes_received < num_bytes:
        chunk = sock.recv(num_bytes - bytes_received)
        if not chunk:
            raise EOFError("Connection closed")
        chunks.append(chunk)
        bytes_received += len(chunk)
    
    return b''.join(chunks)


def parse_message(payload: bytes) -> Message:
    """
    Parse a message payload.
    
    Args:
        payload: JSON payload bytes
    
    Returns:
        Parsed Message object
    
    Raises:
        ValidationError: If message is invalid
    """
    try:
        data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")
    except UnicodeDecodeError as e:
        raise ValidationError(f"Invalid UTF-8: {e}")
    
    # Validate structure
    if not isinstance(data, dict):
        raise ValidationError("Message must be a JSON object")
    if "header" not in data:
        raise ValidationError("Missing header")
    if "data" not in data:
        raise ValidationError("Missing data")
    
    # Parse and validate
    message = Message.from_dict(data)
    message.validate()
    
    return message


def create_event_message(
    agent_id: str,
    token_id: str,
    path: str,
    event_type: str,
    **extra_fields
) -> Message:
    """
    Create an event message (honeytoken access).
    
    Args:
        agent_id: Agent identifier
        token_id: Honeytoken identifier
        path: File path that was accessed
        event_type: Event type ("created", "modified", "opened", "deleted")
        **extra_fields: Additional event data
    
    Returns:
        Event Message
    """
    data = {
        "token_id": token_id,
        "path": path,
        "event_type": event_type,
        **extra_fields
    }
    
    return create_message(agent_id, "event", data)


def create_heartbeat_message(agent_id: str, status: str = "healthy") -> Message:
    """
    Create a heartbeat message.
    
    Args:
        agent_id: Agent identifier
        status: Agent status ("healthy", "warning", "error")
    
    Returns:
        Heartbeat Message
    """
    data = {
        "status": status,
        "uptime": time.time()
    }
    
    return create_message(agent_id, "heartbeat", data)


# Example usage and testing
if __name__ == "__main__":
    print("HoneyGrid Protocol Module - Test")
    print("=" * 60)
    
    # Create an event message
    msg = create_event_message(
        agent_id="agent-001",
        token_id="token-abc123",
        path="C:\\honeytokens\\secret.docx",
        event_type="opened"
    )
    
    print("\n1. Created Event Message:")
    print(json.dumps(msg.to_dict(), indent=2))
    
    # Frame the message
    framed = frame_message(msg)
    print(f"\n2. Framed Message: {len(framed)} bytes")
    print(f"   Length prefix: {struct.unpack('!I', framed[:4])[0]} bytes")
    
    # Parse it back
    payload = framed[4:]
    parsed = parse_message(payload)
    print("\n3. Parsed Message:")
    print(f"   Agent: {parsed.header.agent_id}")
    print(f"   Type: {parsed.header.msg_type}")
    print(f"   Token: {parsed.data['token_id']}")
    print(f"   Path: {parsed.data['path']}")
    
    # Validate nonce uniqueness
    print("\n4. Nonce Uniqueness Test:")
    nonces = [generate_nonce() for _ in range(5)]
    print(f"   Generated 5 unique nonces:")
    for i, nonce in enumerate(nonces, 1):
        print(f"   {i}. {nonce}")
    print(f"   All unique: {len(nonces) == len(set(nonces))}")
    
    print("\n" + "=" * 60)
    print("✓ Protocol tests passed!")
