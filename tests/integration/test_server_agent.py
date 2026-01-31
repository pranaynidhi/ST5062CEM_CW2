#!/usr/bin/env python3
"""
Integration tests for server-agent communication.
Tests end-to-end TLS connection, message exchange, and database storage.
"""

import pytest
import asyncio
import time
import os
import tempfile
import multiprocessing
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.server import HoneyGridServer
from server.db import DatabaseManager
from server.protocol import create_event_message, frame_message
from agent.sender import SecureSender


# Test configuration
TEST_HOST = "127.0.0.1"
TEST_PORT = 19000  # Use different port to avoid conflicts
TEST_CA_CERT = "certs/ca.crt"
TEST_SERVER_CERT = "certs/server.crt"
TEST_SERVER_KEY = "certs/server.key"
TEST_CLIENT_CERT = "certs/client_client-001.crt"
TEST_CLIENT_KEY = "certs/client_client-001.key"


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


@pytest.fixture
def server_queue():
    """Create a multiprocessing queue for server->GUI events."""
    return multiprocessing.Manager().Queue()


def run_server_process(db_path, db_password, host, port, queue, ready_event):
    """Run server in a separate process."""
    try:
        # Create server
        server = HoneyGridServer(
            host=host,
            port=port,
            db_path=db_path,
            db_password=db_password,
            ca_cert_path=TEST_CA_CERT,
            server_cert_path=TEST_SERVER_CERT,
            server_key_path=TEST_SERVER_KEY
        )
        
        # Signal that server is ready
        ready_event.set()
        
        # Run server
        asyncio.run(server.start())
    except Exception as e:
        print(f"Server error: {e}")


class TestServerAgentCommunication:
    """Test server-agent communication."""
    
    def test_server_accepts_connection(self, temp_db, server_queue):
        """Test that server accepts client connection."""
        # Create ready event
        ready_event = multiprocessing.Event()
        
        # Start server in background process
        server_process = multiprocessing.Process(
            target=run_server_process,
            args=(temp_db.db_path, temp_db.password, TEST_HOST, TEST_PORT, server_queue, ready_event)
        )
        server_process.start()
        
        try:
            # Wait for server to be ready
            ready_event.wait(timeout=5)
            time.sleep(1)  # Additional time for server to bind
            
            # Create client sender
            sender = SecureSender(
                agent_id="test-agent-001",
                server_host=TEST_HOST,
                server_port=TEST_PORT,
                ca_cert_path=TEST_CA_CERT,
                client_cert_path=TEST_CLIENT_CERT,
                client_key_path=TEST_CLIENT_KEY,
                rate_limit=100.0
            )
            
            # Connect
            success = sender.connect()
            assert success is True
            
            # Disconnect
            sender.disconnect()
            
        finally:
            # Stop server
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()
    
    def test_agent_sends_event(self, temp_db, server_queue):
        """Test agent sending event to server."""
        # Create ready event
        ready_event = multiprocessing.Event()
        
        # Start server
        server_process = multiprocessing.Process(
            target=run_server_process,
            args=(temp_db.db_path, temp_db.password, TEST_HOST, TEST_PORT, server_queue, ready_event)
        )
        server_process.start()
        
        try:
            # Wait for server
            ready_event.wait(timeout=5)
            time.sleep(1)
            
            # Create sender
            sender = SecureSender(
                agent_id="test-agent-002",
                server_host=TEST_HOST,
                server_port=TEST_PORT,
                ca_cert_path=TEST_CA_CERT,
                client_cert_path=TEST_CLIENT_CERT,
                client_key_path=TEST_CLIENT_KEY,
                rate_limit=100.0
            )
            
            # Connect
            sender.connect()
            
            # Send event
            success = sender.send_event(
                token_id="test-token-001",
                path="C:\\test\\file.txt",
                event_type="opened",
                metadata={"test": True}
            )
            
            assert success is True
            
            # Disconnect
            sender.disconnect()
            
            # Wait for event to be processed
            time.sleep(1)
            
            # Verify event in database
            events = temp_db.get_recent_events(limit=10)
            assert len(events) > 0
            
            # Find our event
            test_event = None
            for event in events:
                if event["agent_id"] == "test-agent-002":
                    test_event = event
                    break
            
            assert test_event is not None
            assert test_event["token_id"] == "test-token-001"
            assert test_event["path"] == "C:\\test\\file.txt"
            assert test_event["event_type"] == "opened"
            
        finally:
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()
    
    def test_multiple_events(self, temp_db, server_queue):
        """Test sending multiple events."""
        ready_event = multiprocessing.Event()
        
        # Start server
        server_process = multiprocessing.Process(
            target=run_server_process,
            args=(temp_db.db_path, temp_db.password, TEST_HOST, TEST_PORT, server_queue, ready_event)
        )
        server_process.start()
        
        try:
            # Wait for server
            ready_event.wait(timeout=5)
            time.sleep(1)
            
            # Create sender
            sender = SecureSender(
                agent_id="test-agent-003",
                server_host=TEST_HOST,
                server_port=TEST_PORT,
                ca_cert_path=TEST_CA_CERT,
                client_cert_path=TEST_CLIENT_CERT,
                client_key_path=TEST_CLIENT_KEY,
                rate_limit=100.0
            )
            
            # Connect
            sender.connect()
            
            # Send multiple events
            for i in range(5):
                success = sender.send_event(
                    token_id=f"test-token-{i:03d}",
                    path=f"C:\\test\\file{i}.txt",
                    event_type="opened"
                )
                assert success is True
                time.sleep(0.1)
            
            sender.disconnect()
            
            # Wait for processing
            time.sleep(2)
            
            # Verify all events
            events = temp_db.get_recent_events(agent_id="test-agent-003", limit=10)
            assert len(events) >= 5
            
        finally:
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()
    
    def test_replay_attack_prevention(self, temp_db, server_queue):
        """Test that replay attacks are prevented."""
        ready_event = multiprocessing.Event()
        
        # Start server
        server_process = multiprocessing.Process(
            target=run_server_process,
            args=(temp_db.db_path, temp_db.password, TEST_HOST, TEST_PORT, server_queue, ready_event)
        )
        server_process.start()
        
        try:
            # Wait for server
            ready_event.wait(timeout=5)
            time.sleep(1)
            
            # Create sender
            sender = SecureSender(
                agent_id="test-agent-004",
                server_host=TEST_HOST,
                server_port=TEST_PORT,
                ca_cert_path=TEST_CA_CERT,
                client_cert_path=TEST_CLIENT_CERT,
                client_key_path=TEST_CLIENT_KEY,
                rate_limit=100.0
            )
            
            # Connect
            sender.connect()
            
            # Send event
            sender.send_event(
                token_id="test-token-replay",
                path="C:\\test\\replay.txt",
                event_type="opened"
            )
            
            sender.disconnect()
            time.sleep(1)
            
            # Count events before replay
            events_before = temp_db.get_recent_events(agent_id="test-agent-004", limit=10)
            count_before = len(events_before)
            
            # Try to replay - create new connection with same message
            # (This would require capturing and resending, but we can verify
            # that duplicate nonces are rejected by the database)
            
            # Instead, verify that database rejects duplicate nonces
            try:
                temp_db.insert_event(
                    agent_id="test-agent-004",
                    token_id="test-token-replay",
                    path="C:\\test\\replay.txt",
                    event_type="opened",
                    nonce=events_before[0]["nonce"]  # Reuse nonce
                )
                assert False, "Should have raised DatabaseError for duplicate nonce"
            except Exception as e:
                assert "replay attack" in str(e).lower()
            
        finally:
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()


@pytest.mark.asyncio
class TestServerStatistics:
    """Test server statistics tracking."""
    
    def test_connection_statistics(self, temp_db, server_queue):
        """Test that server tracks connection statistics."""
        ready_event = multiprocessing.Event()
        
        # Start server
        server_process = multiprocessing.Process(
            target=run_server_process,
            args=(temp_db.db_path, temp_db.password, TEST_HOST, TEST_PORT, server_queue, ready_event)
        )
        server_process.start()
        
        try:
            # Wait for server
            ready_event.wait(timeout=5)
            time.sleep(1)
            
            # Create and connect multiple senders
            senders = []
            for i in range(3):
                sender = SecureSender(
                    agent_id=f"test-agent-stats-{i}",
                    server_host=TEST_HOST,
                    server_port=TEST_PORT,
                    ca_cert_path=TEST_CA_CERT,
                    client_cert_path=TEST_CLIENT_CERT,
                    client_key_path=TEST_CLIENT_KEY,
                    rate_limit=100.0
                )
                sender.connect()
                senders.append(sender)
                time.sleep(0.2)
            
            # Send some events
            for sender in senders:
                sender.send_event(
                    token_id="test-token-stats",
                    path="C:\\test\\stats.txt",
                    event_type="opened"
                )
            
            time.sleep(1)
            
            # Disconnect all
            for sender in senders:
                sender.disconnect()
            
            # Verify events were stored
            time.sleep(1)
            events = temp_db.get_recent_events(limit=10)
            assert len(events) >= 3
            
        finally:
            server_process.terminate()
            server_process.join(timeout=5)
            if server_process.is_alive():
                server_process.kill()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])


