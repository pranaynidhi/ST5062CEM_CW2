#!/usr/bin/env python3
"""Unit tests for HoneyGrid agent."""

import pytest
import tempfile
import os
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.agent import HoneyGridAgent, load_config_from_file


class TestAgentInit:
    """Test agent initialization."""
    
    def test_agent_basic_init(self):
        """Test basic agent initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_mapping = {"t1": "/tmp/honey"}
            
            agent = HoneyGridAgent(
                agent_id="test-agent",
                server_host="127.0.0.1",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping=token_mapping,
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client_client-001.crt",
                client_key_path="certs/client_client-001.key"
            )
            
            assert agent.agent_id == "test-agent"
            assert agent.server_host == "127.0.0.1"
            assert agent.server_port == 9000
            assert agent.watch_paths == [tmpdir]
            assert agent.token_mapping == token_mapping
            assert not agent.is_running
    
    def test_agent_init_with_custom_params(self):
        """Test agent initialization with custom parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="custom-agent",
                server_host="192.168.1.1",
                server_port=8888,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="ca.crt",
                client_cert_path="client.crt",
                client_key_path="client.key",
                heartbeat_interval=60.0,
                recursive=False
            )
            
            assert agent.agent_id == "custom-agent"
            assert agent.heartbeat_interval == 60.0
            assert agent.recursive is False
    
    def test_agent_init_paths(self):
        """Test that agent stores certificate paths correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="path/to/ca.crt",
                client_cert_path="path/to/client.crt",
                client_key_path="path/to/client.key"
            )
            
            assert agent.ca_cert_path == "path/to/ca.crt"
            assert agent.client_cert_path == "path/to/client.crt"
            assert agent.client_key_path == "path/to/client.key"
    
    def test_agent_components_initially_none(self):
        """Test that agent components are None initially."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="ca.crt",
                client_cert_path="client.crt",
                client_key_path="client.key"
            )
            
            assert agent.monitor is None
            assert agent.sender is None
            assert agent.sender_thread is None
    
    def test_agent_event_queue_created(self):
        """Test that event queue is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="ca.crt",
                client_cert_path="client.crt",
                client_key_path="client.key"
            )
            
            assert agent.event_queue is not None
            assert hasattr(agent.event_queue, 'put')
            assert hasattr(agent.event_queue, 'get')


class TestConfigLoading:
    """Test configuration loading."""
    
    def test_load_config_from_file(self):
        """Test loading config from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "agent_id": "test-agent",
                "server_host": "192.168.1.1",
                "server_port": 9000,
                "watch_paths": ["/tmp/honey1", "/tmp/honey2"],
                "token_mapping": {"t1": "/tmp/honey1"}
            }
            json.dump(config, f)
            fname = f.name
        
        try:
            loaded = load_config_from_file(fname)
            assert loaded["agent_id"] == "test-agent"
            assert loaded["server_host"] == "192.168.1.1"
            assert loaded["server_port"] == 9000
            assert len(loaded["watch_paths"]) == 2
        finally:
            os.unlink(fname)
    
    def test_load_config_complex(self):
        """Test loading complex configuration."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            config = {
                "agent_id": "complex-agent",
                "server_host": "example.com",
                "server_port": 8443,
                "watch_paths": ["/var/honeytokens", "/opt/decoys"],
                "token_mapping": {
                    "token1": "/var/honeytokens/file1.txt",
                    "token2": "/opt/decoys/file2.doc"
                },
                "heartbeat_interval": 45.0,
                "recursive": True
            }
            json.dump(config, f)
            fname = f.name
        
        try:
            loaded = load_config_from_file(fname)
            assert loaded["heartbeat_interval"] == 45.0
            assert loaded["recursive"] is True
            assert len(loaded["token_mapping"]) == 2
        finally:
            os.unlink(fname)


class TestAgentLifecycle:
    """Test agent start/stop lifecycle."""
    
    def test_agent_is_running_initially_false(self):
        """Test agent is_running is False initially."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            assert agent.is_running is False
    
    def test_agent_stop_when_not_running(self):
        """Test stop is safe when agent not running."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            # Should not raise exception
            agent.stop()
            assert agent.is_running is False
    
    def test_agent_manager_created(self):
        """Test multiprocessing Manager is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            assert agent.manager is not None
            assert agent.event_queue is not None


class TestAgentPaths:
    """Test agent path handling."""
    
    def test_agent_multiple_watch_paths(self):
        """Test agent with multiple watch paths."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                agent = HoneyGridAgent(
                    agent_id="test",
                    server_host="localhost",
                    server_port=9000,
                    watch_paths=[tmpdir1, tmpdir2],
                    token_mapping={},
                    ca_cert_path="certs/ca.crt",
                    client_cert_path="certs/client.crt",
                    client_key_path="certs/client.key"
                )
                assert len(agent.watch_paths) == 2
                assert tmpdir1 in agent.watch_paths
                assert tmpdir2 in agent.watch_paths
    
    def test_agent_empty_watch_paths(self):
        """Test agent with empty watch paths."""
        agent = HoneyGridAgent(
            agent_id="test",
            server_host="localhost",
            server_port=9000,
            watch_paths=[],
            token_mapping={},
            ca_cert_path="certs/ca.crt",
            client_cert_path="certs/client.crt",
            client_key_path="certs/client.key"
        )
        assert agent.watch_paths == []


class TestAgentTokenMapping:
    """Test agent token mapping."""
    
    def test_agent_empty_token_mapping(self):
        """Test agent with empty token mapping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            assert agent.token_mapping == {}
    
    def test_agent_multiple_token_mappings(self):
        """Test agent with multiple token mappings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mapping = {
                "token1": "/path/to/file1.txt",
                "token2": "/path/to/file2.doc",
                "token3": "/path/to/file3.pdf"
            }
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping=mapping,
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            assert len(agent.token_mapping) == 3
            assert agent.token_mapping["token1"] == "/path/to/file1.txt"


class TestAgentServerConfig:
    """Test agent server configuration."""
    
    def test_agent_different_ports(self):
        """Test agent with different server ports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for port in [8443, 9000, 10000]:
                agent = HoneyGridAgent(
                    agent_id="test",
                    server_host="localhost",
                    server_port=port,
                    watch_paths=[tmpdir],
                    token_mapping={},
                    ca_cert_path="certs/ca.crt",
                    client_cert_path="certs/client.crt",
                    client_key_path="certs/client.key"
                )
                assert agent.server_port == port
    
    def test_agent_different_hosts(self):
        """Test agent with different server hosts."""
        hosts = ["localhost", "127.0.0.1", "example.com", "192.168.1.1"]
        with tempfile.TemporaryDirectory() as tmpdir:
            for host in hosts:
                agent = HoneyGridAgent(
                    agent_id="test",
                    server_host=host,
                    server_port=9000,
                    watch_paths=[tmpdir],
                    token_mapping={},
                    ca_cert_path="certs/ca.crt",
                    client_cert_path="certs/client.crt",
                    client_key_path="certs/client.key"
                )
                assert agent.server_host == host


class TestAgentHeartbeat:
    """Test agent heartbeat configuration."""
    
    def test_agent_default_heartbeat(self):
        """Test agent default heartbeat interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            assert agent.heartbeat_interval == 30.0
    
    def test_agent_custom_heartbeat(self):
        """Test agent custom heartbeat interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for interval in [10.0, 60.0, 120.0]:
                agent = HoneyGridAgent(
                    agent_id="test",
                    server_host="localhost",
                    server_port=9000,
                    watch_paths=[tmpdir],
                    token_mapping={},
                    ca_cert_path="certs/ca.crt",
                    client_cert_path="certs/client.crt",
                    client_key_path="certs/client.key",
                    heartbeat_interval=interval
                )
                assert agent.heartbeat_interval == interval


class TestAgentRecursive:
    """Test agent recursive monitoring option."""
    
    def test_agent_recursive_default(self):
        """Test agent recursive is True by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key"
            )
            assert agent.recursive is True
    
    def test_agent_recursive_false(self):
        """Test agent recursive can be set to False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            agent = HoneyGridAgent(
                agent_id="test",
                server_host="localhost",
                server_port=9000,
                watch_paths=[tmpdir],
                token_mapping={},
                ca_cert_path="certs/ca.crt",
                client_cert_path="certs/client.crt",
                client_key_path="certs/client.key",
                recursive=False
            )
            assert agent.recursive is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
