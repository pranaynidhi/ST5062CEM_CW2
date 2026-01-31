#!/usr/bin/env python3
"""
HoneyGrid Agent
Main agent coordinator that runs file system monitoring and secure event transmission.
"""

import argparse
import logging
import signal
import sys
import time
import threading
from pathlib import Path
from multiprocessing import Manager
from typing import List, Dict, Optional

from agent.monitor import FSMonitor, MonitorEvent
from agent.sender import SenderProcess


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HoneyGridAgent:
    """
    Main HoneyGrid agent coordinator.
    Manages file monitoring and event transmission.
    """
    
    def __init__(
        self,
        agent_id: str,
        server_host: str,
        server_port: int,
        watch_paths: List[str],
        token_mapping: Dict[str, str],
        ca_cert_path: str,
        client_cert_path: str,
        client_key_path: str,
        heartbeat_interval: float = 30.0,
        recursive: bool = True
    ):
        """
        Initialize HoneyGrid agent.
        
        Args:
            agent_id: Unique agent identifier
            server_host: Server hostname/IP
            server_port: Server port
            watch_paths: List of paths to monitor
            token_mapping: Map of paths to token IDs
            ca_cert_path: CA certificate path
            client_cert_path: Client certificate path
            client_key_path: Client private key path
            heartbeat_interval: Seconds between heartbeats
            recursive: Watch directories recursively
        """
        self.agent_id = agent_id
        self.server_host = server_host
        self.server_port = server_port
        self.watch_paths = watch_paths
        self.token_mapping = token_mapping
        self.ca_cert_path = ca_cert_path
        self.client_cert_path = client_cert_path
        self.client_key_path = client_key_path
        self.heartbeat_interval = heartbeat_interval
        self.recursive = recursive
        
        # Shared event queue
        self.manager = Manager()
        self.event_queue = self.manager.Queue()
        
        # Components
        self.monitor = None
        self.sender = None
        self.sender_thread = None
        
        self.is_running = False
    
    def start(self):
        """Start the agent."""
        if self.is_running:
            logger.warning("Agent already running")
            return
        
        logger.info("=" * 60)
        logger.info(f"HoneyGrid Agent Starting: {self.agent_id}")
        logger.info("=" * 60)
        
        # Initialize monitor
        logger.info("Initializing file system monitor...")
        self.monitor = FSMonitor(
            event_queue=self.event_queue,
            watch_paths=self.watch_paths,
            token_mapping=self.token_mapping,
            recursive=self.recursive,
            verbose=True
        )
        
        # Start monitor
        self.monitor.start()
        logger.info(f"✓ Monitoring {len(self.watch_paths)} path(s)")
        
        # Initialize sender
        logger.info("Initializing secure sender...")
        self.sender = SenderProcess(
            event_queue=self.event_queue,
            agent_id=self.agent_id,
            server_host=self.server_host,
            server_port=self.server_port,
            ca_cert_path=self.ca_cert_path,
            client_cert_path=self.client_cert_path,
            client_key_path=self.client_key_path,
            heartbeat_interval=self.heartbeat_interval
        )
        
        # Start sender in separate thread
        self.sender_thread = threading.Thread(
            target=self.sender.run,
            daemon=True
        )
        self.sender_thread.start()
        logger.info(f"✓ Connected to server: {self.server_host}:{self.server_port}")
        
        self.is_running = True
        logger.info("=" * 60)
        logger.info("✓ Agent running (Ctrl+C to stop)")
        logger.info("=" * 60)
    
    def stop(self):
        """Stop the agent."""
        if not self.is_running:
            return
        
        logger.info("\nStopping agent...")
        
        # Stop monitor
        if self.monitor:
            self.monitor.stop()
            logger.info("✓ Monitor stopped")
        
        # Stop sender
        if self.sender:
            self.sender.stop()
            if self.sender_thread and self.sender_thread.is_alive():
                self.sender_thread.join(timeout=5)
            logger.info("✓ Sender stopped")
        
        self.is_running = False
        logger.info("✓ Agent stopped")
    
    def run(self):
        """Run the agent indefinitely."""
        self.start()
        
        try:
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        finally:
            self.stop()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def load_config_from_file(config_path: str) -> Dict:
    """
    Load agent configuration from file.
    
    Args:
        config_path: Path to config file
    
    Returns:
        Configuration dictionary
    """
    import json
    
    with open(config_path, 'r') as f:
        return json.load(f)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="HoneyGrid Agent - Distributed Honeytoken Monitor"
    )
    
    # Agent configuration
    parser.add_argument(
        "--agent-id",
        required=True,
        help="Unique agent identifier"
    )
    
    # Server configuration
    parser.add_argument(
        "--server-host",
        required=True,
        help="Server hostname/IP"
    )
    parser.add_argument(
        "--server-port",
        type=int,
        default=9000,
        help="Server port (default: 9000)"
    )
    
    # Certificates
    parser.add_argument(
        "--ca-cert",
        default="certs/ca.crt",
        help="CA certificate path"
    )
    parser.add_argument(
        "--client-cert",
        help="Client certificate path (default: certs/client_{agent-id}.crt)"
    )
    parser.add_argument(
        "--client-key",
        help="Client private key path (default: certs/client_{agent-id}.key)"
    )
    
    # Monitoring configuration
    parser.add_argument(
        "--watch-path",
        action="append",
        dest="watch_paths",
        help="Path to monitor (can be specified multiple times)"
    )
    parser.add_argument(
        "--token-id",
        action="append",
        dest="token_ids",
        help="Token ID for corresponding watch path"
    )
    parser.add_argument(
        "--config",
        help="Load configuration from JSON file"
    )
    
    args = parser.parse_args()
    
    # Load config from file if specified
    if args.config:
        config = load_config_from_file(args.config)
        agent_id = config.get("agent_id", args.agent_id)
        server_host = config.get("server_host", args.server_host)
        server_port = config.get("server_port", args.server_port)
        watch_paths = config.get("watch_paths", [])
        token_mapping = config.get("token_mapping", {})
    else:
        agent_id = args.agent_id
        server_host = args.server_host
        server_port = args.server_port
        
        # Build token mapping from command line args
        if not args.watch_paths:
            logger.error("No watch paths specified. Use --watch-path or --config")
            sys.exit(1)
        
        watch_paths = args.watch_paths
        token_ids = args.token_ids or [f"token-{i:03d}" for i in range(len(watch_paths))]
        
        if len(watch_paths) != len(token_ids):
            logger.error("Number of watch paths must match number of token IDs")
            sys.exit(1)
        
        token_mapping = dict(zip(watch_paths, token_ids))
    
    # Set certificate paths
    ca_cert = args.ca_cert
    client_cert = args.client_cert or f"certs/client_{agent_id}.crt"
    client_key = args.client_key or f"certs/client_{agent_id}.key"
    
    # Verify certificates exist
    for cert_file in [ca_cert, client_cert, client_key]:
        if not Path(cert_file).exists():
            logger.error(f"Certificate file not found: {cert_file}")
            logger.error("Run: python scripts/generate_certs.py")
            sys.exit(1)
    
    # Verify watch paths exist
    for path in watch_paths:
        if not Path(path).exists():
            logger.warning(f"Watch path does not exist: {path}")
    
    # Create agent
    agent = HoneyGridAgent(
        agent_id=agent_id,
        server_host=server_host,
        server_port=server_port,
        watch_paths=watch_paths,
        token_mapping=token_mapping,
        ca_cert_path=ca_cert,
        client_cert_path=client_cert,
        client_key_path=client_key
    )
    
    # Handle signals
    def signal_handler(sig, frame):
        logger.info("\nReceived signal, shutting down...")
        agent.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run agent
    agent.run()


if __name__ == "__main__":
    main()
