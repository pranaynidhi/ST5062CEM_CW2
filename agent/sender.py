#!/usr/bin/env python3
"""
HoneyGrid Secure Sender
TLS client for securely transmitting events to the server.
Includes rate limiting and connection management.
"""

import ssl
import socket
import time
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from multiprocessing import Queue
from collections import deque

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.protocol import (
    Message,
    create_event_message,
    create_heartbeat_message,
    frame_message,
    read_frame_sync,
    parse_message,
    ProtocolError
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter.
    Limits events per second with burst capacity.
    """
    
    def __init__(self, rate: float = 10.0, burst: int = 20):
        """
        Initialize rate limiter.
        
        Args:
            rate: Events per second (refill rate)
            burst: Maximum burst capacity (bucket size)
        """
        self.rate = rate  # tokens per second
        self.burst = burst  # max tokens
        self.tokens = float(burst)  # current tokens
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on rate
        new_tokens = elapsed * self.rate
        self.tokens = min(self.burst, self.tokens + new_tokens)
        self.last_refill = now
    
    def acquire(self, tokens: int = 1, blocking: bool = True, timeout: float = None) -> bool:
        """
        Acquire tokens for sending.
        
        Args:
            tokens: Number of tokens to acquire
            blocking: Wait for tokens if unavailable
            timeout: Maximum wait time (None = infinite)
        
        Returns:
            True if tokens acquired, False otherwise
        """
        start_time = time.time()
        
        while True:
            with self.lock:
                self._refill()
                
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
                
                if not blocking:
                    return False
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
            
            # Wait before retry
            time.sleep(0.01)
    
    def get_tokens(self) -> float:
        """Get current token count."""
        with self.lock:
            self._refill()
            return self.tokens


class ConnectionError(Exception):
    """Raised when connection fails."""
    pass


class SecureSender:
    """
    Secure TLS client for sending events to server.
    """
    
    def __init__(
        self,
        agent_id: str,
        server_host: str,
        server_port: int,
        ca_cert_path: str,
        client_cert_path: str,
        client_key_path: str,
        rate_limit: float = 10.0,
        burst_limit: int = 20,
        reconnect_delay: float = 5.0
    ):
        """
        Initialize secure sender.
        
        Args:
            agent_id: Agent identifier
            server_host: Server hostname/IP
            server_port: Server port
            ca_cert_path: Path to CA certificate
            client_cert_path: Path to client certificate
            client_key_path: Path to client private key
            rate_limit: Events per second limit
            burst_limit: Burst capacity
            reconnect_delay: Delay between reconnection attempts
        """
        self.agent_id = agent_id
        self.server_host = server_host
        self.server_port = server_port
        self.ca_cert_path = Path(ca_cert_path)
        self.client_cert_path = Path(client_cert_path)
        self.client_key_path = Path(client_key_path)
        
        self.rate_limiter = RateLimiter(rate_limit, burst_limit)
        self.reconnect_delay = reconnect_delay
        
        self.socket = None
        self.ssl_socket = None
        self.is_connected = False
        self.send_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "sent": 0,
            "failed": 0,
            "rate_limited": 0,
            "reconnects": 0
        }
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS client."""
        # Create context for TLS client
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        # Load CA certificate for server verification
        context.load_verify_locations(str(self.ca_cert_path))
        
        # Load client certificate and key for mutual TLS
        context.load_cert_chain(
            certfile=str(self.client_cert_path),
            keyfile=str(self.client_key_path)
        )
        
        # Require certificate verification
        context.check_hostname = False  # We're using IP addresses
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Use strong ciphers only
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return context
    
    def connect(self) -> bool:
        """
        Connect to server with TLS.
        
        Returns:
            True if connection successful
        """
        if self.is_connected:
            logger.warning("Already connected")
            return True
        
        try:
            logger.info(f"Connecting to {self.server_host}:{self.server_port}...")
            
            # Create socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            
            # Create SSL context
            ssl_context = self._create_ssl_context()
            
            # Wrap socket with TLS
            self.ssl_socket = ssl_context.wrap_socket(
                self.socket,
                server_hostname=self.server_host
            )
            
            # Connect
            self.ssl_socket.connect((self.server_host, self.server_port))
            
            self.is_connected = True
            logger.info(f"✓ Connected to server (TLS {self.ssl_socket.version()})")
            
            # Send initial heartbeat
            self._send_heartbeat()
            
            return True
        
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False
            self._cleanup_socket()
            return False
    
    def disconnect(self):
        """Disconnect from server."""
        if not self.is_connected:
            return
        
        logger.info("Disconnecting from server...")
        self.is_connected = False
        self._cleanup_socket()
    
    def _cleanup_socket(self):
        """Clean up socket resources."""
        if self.ssl_socket:
            try:
                self.ssl_socket.close()
            except:
                pass
            self.ssl_socket = None
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def _reconnect(self) -> bool:
        """Attempt to reconnect to server."""
        logger.info("Attempting to reconnect...")
        self.stats["reconnects"] += 1
        
        self._cleanup_socket()
        time.sleep(self.reconnect_delay)
        
        return self.connect()
    
    def _send_heartbeat(self):
        """Send heartbeat message to server."""
        try:
            msg = create_heartbeat_message(self.agent_id, status="healthy")
            self._send_message(msg, rate_limit=False)
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")
    
    def _send_message(self, message: Message, rate_limit: bool = True) -> bool:
        """
        Send a message to server.
        
        Args:
            message: Message to send
            rate_limit: Apply rate limiting
        
        Returns:
            True if sent successfully
        """
        # Rate limiting
        if rate_limit:
            if not self.rate_limiter.acquire(timeout=5.0):
                logger.warning("Rate limit exceeded, dropping message")
                self.stats["rate_limited"] += 1
                return False
        
        # Ensure connection
        if not self.is_connected:
            if not self._reconnect():
                return False
        
        # Send with lock
        with self.send_lock:
            try:
                # Frame message
                framed = frame_message(message)
                
                # Send
                self.ssl_socket.sendall(framed)
                
                self.stats["sent"] += 1
                return True
            
            except Exception as e:
                logger.error(f"Send failed: {e}")
                self.stats["failed"] += 1
                self.is_connected = False
                return False
    
    def send_event(
        self,
        token_id: str,
        path: str,
        event_type: str,
        **extra_fields
    ) -> bool:
        """
        Send an event message.
        
        Args:
            token_id: Honeytoken identifier
            path: File path
            event_type: Event type
            **extra_fields: Additional event data
        
        Returns:
            True if sent successfully
        """
        try:
            msg = create_event_message(
                self.agent_id,
                token_id,
                path,
                event_type,
                **extra_fields
            )
            
            success = self._send_message(msg, rate_limit=True)
            
            if success:
                logger.info(
                    f"📤 Sent event: {event_type} - {path} (token: {token_id})"
                )
            
            return success
        
        except Exception as e:
            logger.error(f"Failed to create/send event: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get sender statistics."""
        return {
            **self.stats,
            "connected": self.is_connected,
            "rate_tokens": self.rate_limiter.get_tokens()
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


class SenderProcess:
    """
    Process that continuously sends events from a queue.
    """
    
    def __init__(
        self,
        event_queue: Queue,
        agent_id: str,
        server_host: str,
        server_port: int,
        ca_cert_path: str,
        client_cert_path: str,
        client_key_path: str,
        heartbeat_interval: float = 30.0
    ):
        """
        Initialize sender process.
        
        Args:
            event_queue: Queue to pull events from
            agent_id: Agent identifier
            server_host: Server hostname/IP
            server_port: Server port
            ca_cert_path: Path to CA certificate
            client_cert_path: Path to client certificate
            client_key_path: Path to client private key
            heartbeat_interval: Seconds between heartbeats
        """
        self.event_queue = event_queue
        self.agent_id = agent_id
        self.sender = SecureSender(
            agent_id,
            server_host,
            server_port,
            ca_cert_path,
            client_cert_path,
            client_key_path
        )
        self.heartbeat_interval = heartbeat_interval
        self.is_running = False
        self.last_heartbeat = 0
    
    def run(self):
        """Run sender process."""
        logger.info(f"Sender process starting for agent {self.agent_id}")
        
        # Connect to server
        if not self.sender.connect():
            logger.error("Failed to connect to server")
            return
        
        self.is_running = True
        
        try:
            while self.is_running:
                # Send heartbeat if needed
                now = time.time()
                if now - self.last_heartbeat >= self.heartbeat_interval:
                    self.sender._send_heartbeat()
                    self.last_heartbeat = now
                
                # Check for events (non-blocking)
                try:
                    event = self.event_queue.get(timeout=1.0)
                    
                    # Send event
                    self.sender.send_event(
                        token_id=event.token_id,
                        path=event.path,
                        event_type=event.event_type,
                        timestamp=event.timestamp,
                        is_directory=event.is_directory,
                        metadata=event.metadata
                    )
                
                except Exception as e:
                    if "Empty" not in str(e):
                        logger.error(f"Error processing event: {e}")
        
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()
    
    def stop(self):
        """Stop sender process."""
        logger.info("Stopping sender process...")
        self.is_running = False
        self.sender.disconnect()
        
        # Show statistics
        stats = self.sender.get_stats()
        logger.info(f"Statistics: {stats}")


# Example usage and testing
if __name__ == "__main__":
    print("HoneyGrid Secure Sender - Test")
    print("=" * 60)
    
    # Note: This requires server to be running and certificates to exist
    print("\n⚠️  This test requires:")
    print("   1. Server running on localhost:9000")
    print("   2. SSL certificates in certs/ directory")
    print("   3. Run: python scripts/generate_certs.py first")
    print("\nTest Mode: Rate limiter demonstration")
    print("=" * 60)
    
    # Test rate limiter
    print("\n1. Testing Rate Limiter:")
    limiter = RateLimiter(rate=5.0, burst=10)
    print(f"   Config: 5 events/sec, burst=10")
    print(f"   Initial tokens: {limiter.get_tokens():.2f}")
    
    # Consume some tokens
    for i in range(5):
        acquired = limiter.acquire(timeout=0.1)
        print(f"   Request {i+1}: {'✓' if acquired else '✗'} (tokens: {limiter.get_tokens():.2f})")
    
    # Wait for refill
    print(f"\n   Waiting 2 seconds for refill...")
    time.sleep(2)
    print(f"   Tokens after refill: {limiter.get_tokens():.2f}")
    
    # Test sender with mock connection
    print("\n2. Testing Sender (without server):")
    
    cert_dir = Path(__file__).parent.parent / "certs"
    
    if not cert_dir.exists():
        print(f"   ⚠️  Certificate directory not found: {cert_dir}")
        print("   Run: python scripts/generate_certs.py")
    else:
        print(f"   Certificate directory: {cert_dir}")
        
        ca_cert = cert_dir / "ca.crt"
        client_cert = cert_dir / "client_client-001.crt"
        client_key = cert_dir / "client_client-001.key"
        
        if all(p.exists() for p in [ca_cert, client_cert, client_key]):
            print("   ✓ Certificates found")
            
            # Create sender (will fail to connect without server)
            sender = SecureSender(
                agent_id="test-agent",
                server_host="localhost",
                server_port=9000,
                ca_cert_path=str(ca_cert),
                client_cert_path=str(client_cert),
                client_key_path=str(client_key)
            )
            
            print(f"   Created sender for agent: {sender.agent_id}")
            print(f"   Target: {sender.server_host}:{sender.server_port}")
            print(f"   Rate limit: {sender.rate_limiter.rate} events/sec")
            
            # Try to connect (will fail without server)
            print("\n   Attempting connection (will fail without server)...")
            connected = sender.connect()
            print(f"   Connection: {'✓ Success' if connected else '✗ Failed (expected)'}")
            
            if connected:
                # If server is running, send a test event
                sender.send_event(
                    token_id="test-token-001",
                    path="C:\\test\\honeytoken.txt",
                    event_type="opened"
                )
                sender.disconnect()
        else:
            print("   ⚠️  Certificates not found")
            print("   Run: python scripts/generate_certs.py")
    
    print("\n" + "=" * 60)
    print("✓ Sender tests complete!")
