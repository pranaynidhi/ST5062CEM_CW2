#!/usr/bin/env python3
"""
HoneyGrid Server
Asyncio TLS server with mutual authentication, replay protection, and rate limiting.
Receives events from agents and stores them in encrypted database.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import ssl
import time
import logging
from typing import Dict, Set, Optional, Any
from collections import OrderedDict
from queue import Queue
import argparse

from server.protocol import (
    read_frame,
    parse_message,
    Message,
    ProtocolError,
    ValidationError
)
from server.db import DatabaseManager
from server.notifiers import EmailNotifier, DiscordNotifier, NotificationConfig, Severity
from server.config_loader import load_config, get_nested_value, DEFAULT_SERVER_CONFIG
from utils.env_loader import load_env


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env if available
load_env()


class LRUCache:
    """
    LRU cache for nonce replay protection.
    """
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum cache size
        """
        self.cache = OrderedDict()
        self.max_size = max_size
    
    def add(self, key: str):
        """Add key to cache."""
        if key in self.cache:
            # Move to end (most recently used)
            self.cache.move_to_end(key)
        else:
            self.cache[key] = True
            # Remove oldest if over limit
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)
    
    def contains(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self.cache
    
    def size(self) -> int:
        """Get cache size."""
        return len(self.cache)


class ClientHandler:
    """
    Handles individual client connection.
    """
    
    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        db: DatabaseManager,
        nonce_cache: LRUCache,
        event_queue: Queue,
        notifiers: list,
        addr: tuple
    ):
        """
        Initialize client handler.
        
        Args:
            reader: Async stream reader
            writer: Async stream writer
            db: Database manager
            nonce_cache: Nonce cache for replay protection
            event_queue: Queue for GUI notifications
            notifiers: List of notification channels
            addr: Client address
        """
        self.reader = reader
        self.writer = writer
        self.db = db
        self.nonce_cache = nonce_cache
        self.event_queue = event_queue
        self.notifiers = notifiers
        self.addr = addr
        
        self.agent_id = None
        self.is_authenticated = False
        self.message_count = 0
        
        # Get agent certificate info
        ssl_object = writer.get_extra_info('ssl_object')
        if ssl_object:
            peer_cert = ssl_object.getpeercert()
            if peer_cert:
                subject = dict(x[0] for x in peer_cert['subject'])
                self.agent_id = subject.get('commonName', 'unknown')
                logger.info(f"Client connected: {self.agent_id} from {addr[0]}:{addr[1]}")
        
        if not self.agent_id:
            self.agent_id = f"unknown_{addr[0]}_{addr[1]}"
    
    async def handle(self):
        """Handle client connection."""
        try:
            # Register agent in database
            self.db.register_agent(
                agent_id=self.agent_id,
                ip_address=self.addr[0],
                metadata={"port": self.addr[1]}
            )
            
            logger.info(f"[{self.agent_id}] Connection established")
            
            # Message loop
            while True:
                try:
                    # Read message frame
                    payload = await read_frame(self.reader)
                    
                    # Parse message
                    message = parse_message(payload)
                    
                    # Validate and process
                    await self._process_message(message)
                    
                    self.message_count += 1
                
                except EOFError:
                    logger.info(f"[{self.agent_id}] Connection closed by client")
                    break
                
                except ProtocolError as e:
                    logger.warning(f"[{self.agent_id}] Protocol error: {e}")
                    # Don't break connection on protocol errors
                
                except Exception as e:
                    logger.error(f"[{self.agent_id}] Error processing message: {e}")
                    break
        
        finally:
            await self._cleanup()
    
    async def _process_message(self, message: Message):
        """
        Process a received message.
        
        Args:
            message: Parsed message
        """
        # Verify agent ID matches certificate
        if message.header.agent_id != self.agent_id:
            logger.warning(
                f"[{self.agent_id}] Agent ID mismatch: "
                f"message claims {message.header.agent_id}"
            )
            return
        
        # Replay protection: check nonce
        nonce = message.header.nonce
        if self.nonce_cache.contains(nonce):
            logger.warning(
                f"[{self.agent_id}] REPLAY ATTACK DETECTED! "
                f"Duplicate nonce: {nonce}"
            )
            raise ValidationError("Duplicate nonce (replay attack)")
        
        # Add nonce to cache
        self.nonce_cache.add(nonce)
        
        # Process based on message type
        msg_type = message.header.msg_type
        
        if msg_type == "event":
            await self._handle_event(message)
        
        elif msg_type == "heartbeat":
            await self._handle_heartbeat(message)
        
        elif msg_type == "status":
            await self._handle_status(message)
        
        else:
            logger.warning(f"[{self.agent_id}] Unknown message type: {msg_type}")
    
    async def _handle_event(self, message: Message):
        """Handle honeytoken event."""
        data = message.data
        
        logger.warning(
            f"🚨 [{self.agent_id}] HONEYTOKEN TRIGGERED! "
            f"token={data.get('token_id')}, "
            f"path={data.get('path')}, "
            f"type={data.get('event_type')}"
        )
        
        # Store in database
        try:
            event_id = self.db.insert_event(
                agent_id=self.agent_id,
                token_id=data.get('token_id', 'unknown'),
                path=data.get('path', ''),
                event_type=data.get('event_type', 'unknown'),
                nonce=message.header.nonce,
                timestamp=message.header.timestamp,
                data=data
            )
            
            logger.info(f"[{self.agent_id}] Event stored with ID: {event_id}")
            
            # Send notifications
            event_data = {
                'agent_id': self.agent_id,
                'token_id': data.get('token_id', 'unknown'),
                'path': data.get('path', ''),
                'event_type': data.get('event_type', 'unknown'),
                'timestamp': message.header.timestamp,
                'data': data
            }
            
            for notifier in self.notifiers:
                try:
                    sent = await notifier.notify(event_data)
                    logger.info(
                        f"[{self.agent_id}] Notification via {notifier.__class__.__name__}: "
                        f"{'sent' if sent else 'skipped'}"
                    )
                except Exception as e:
                    logger.error(f"Notification failed: {e}")
            
            # Push to GUI queue
            if self.event_queue:
                try:
                    self.event_queue.put_nowait({
                        "type": "event",
                        "agent_id": self.agent_id,
                        "event_id": event_id,
                        "data": data,
                        "timestamp": message.header.timestamp
                    })
                except:
                    pass  # GUI queue full, skip
        
        except Exception as e:
            logger.error(f"[{self.agent_id}] Failed to store event: {e}")
    
    async def _handle_heartbeat(self, message: Message):
        """Handle heartbeat message."""
        data = message.data
        status = data.get('status', 'unknown')
        
        logger.debug(f"[{self.agent_id}] Heartbeat: {status}")
        
        # Update agent status
        self.db.update_agent_status(self.agent_id, status)
    
    async def _handle_status(self, message: Message):
        """Handle status message."""
        data = message.data
        logger.info(f"[{self.agent_id}] Status: {data}")
    
    async def _cleanup(self):
        """Clean up connection."""
        logger.info(
            f"[{self.agent_id}] Disconnected "
            f"(processed {self.message_count} messages)"
        )
        
        # Update agent status to offline
        self.db.update_agent_status(self.agent_id, "offline")
        
        # Close writer
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except:
            pass


class HoneyGridServer:
    """
    Main HoneyGrid server.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9000,
        ca_cert_path: str = "certs/ca.crt",
        server_cert_path: str = "certs/server.crt",
        server_key_path: str = "certs/server.key",
        db_path: str = "data/honeygrid.db",
        db_password: str = "change_this_password",
        max_nonce_cache: int = 1000,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize server.
        
        Args:
            host: Bind address
            port: Bind port
            ca_cert_path: CA certificate path
            server_cert_path: Server certificate path
            server_key_path: Server private key path
            db_path: Database file path
            db_password: Database encryption password
            max_nonce_cache: Maximum nonce cache size
            config: Optional configuration dictionary
        """
        self.host = host
        self.port = port
        self.ca_cert_path = Path(ca_cert_path)
        self.server_cert_path = Path(server_cert_path)
        self.server_key_path = Path(server_key_path)
        self.config = config or {}
        
        # Initialize database
        self.db = DatabaseManager(db_path, db_password)
        self.db.connect()
        
        # Nonce cache for replay protection
        self.nonce_cache = LRUCache(max_nonce_cache)
        
        # Event queue for GUI
        self.event_queue = Queue(maxsize=1000)
        
        # Initialize notifiers
        self.notifiers = self._init_notifiers()
        
        # Health monitoring configuration
        self.agent_timeout = 90  # Seconds before marking agent as offline
        self.health_check_interval = 30  # Check every 30 seconds
        self.health_monitor_task = None
        
        # Server state
        self.server = None
        self.active_connections: Set[asyncio.Task] = set()
        
        # Statistics
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "total_messages": 0,
            "total_events": 0,
            "replay_attempts": 0
        }
    
    def _init_notifiers(self) -> list:
        """Initialize notification channels based on configuration."""
        notifiers = []
        
        # Get notification config
        notif_config_dict = self.config.get('notifications', {})
        
        if not notif_config_dict.get('enabled', False):
            logger.info("Notifications disabled")
            return notifiers
        
        # Parse severity
        min_severity_str = notif_config_dict.get('min_severity', 'low').lower()
        severity_map = {
            'info': Severity.INFO,
            'low': Severity.LOW,
            'medium': Severity.MEDIUM,
            'high': Severity.HIGH,
            'critical': Severity.CRITICAL
        }
        min_severity = severity_map.get(min_severity_str, Severity.LOW)
        
        # Create base config
        base_config = NotificationConfig(
            enabled=True,
            rate_limit_seconds=notif_config_dict.get('rate_limit_seconds', 60),
            batch_mode=notif_config_dict.get('batch_mode', False),
            batch_interval_seconds=notif_config_dict.get('batch_interval_seconds', 3600),
            min_severity=min_severity
        )
        
        # Initialize Email notifier
        email_config = notif_config_dict.get('email', {})
        if email_config.get('enabled', False):
            try:
                email_notifier = EmailNotifier(
                    config=base_config,
                    smtp_host=email_config.get('smtp_host', 'smtp.gmail.com'),
                    smtp_port=email_config.get('smtp_port', 587),
                    smtp_username=email_config.get('smtp_username', ''),
                    smtp_password=email_config.get('smtp_password', ''),
                    from_address=email_config.get('from_address', 'honeygrid@example.com'),
                    to_addresses=email_config.get('to_addresses', []),
                    use_tls=email_config.get('use_tls', True)
                )
                notifiers.append(email_notifier)
                logger.info(f"✓ Email notifications enabled ({len(email_notifier.to_addresses)} recipients)")
            except Exception as e:
                logger.error(f"Failed to initialize email notifier: {e}")
        
        # Initialize Discord notifier
        discord_config = notif_config_dict.get('discord', {})
        if discord_config.get('enabled', False):
            try:
                discord_notifier = DiscordNotifier(
                    config=base_config,
                    webhook_url=discord_config.get('webhook_url', ''),
                    username=discord_config.get('username', 'HoneyGrid Bot'),
                    avatar_url=discord_config.get('avatar_url', None)
                )
                notifiers.append(discord_notifier)
                logger.info("✓ Discord notifications enabled")
            except Exception as e:
                logger.error(f"Failed to initialize Discord notifier: {e}")
        
        return notifiers
    
    async def _check_agent_health(self):
        """Background task to check agent health and mark stale agents as offline."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                current_time = int(time.time())
                agents = self.db.get_all_agents()
                
                for agent in agents:
                    last_seen = agent.get('last_seen', 0)
                    time_since_seen = current_time - last_seen
                    
                    # Check if agent has timed out
                    if time_since_seen > self.agent_timeout:
                        if agent.get('status') != 'offline':
                            logger.warning(
                                f"Agent {agent['agent_id']} timed out "
                                f"(last seen {time_since_seen}s ago)"
                            )
                            self.db.update_agent_status(agent['agent_id'], 'offline')
                    elif time_since_seen > (self.agent_timeout * 0.7):
                        # Warning state if 70% of timeout reached
                        if agent.get('status') == 'healthy':
                            logger.info(f"Agent {agent['agent_id']} entering warning state")
                            self.db.update_agent_status(agent['agent_id'], 'warning')
            
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    def _create_ssl_context(self) -> ssl.SSLContext:
        """Create SSL context for TLS server."""
        # Create context for TLS server
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        # Load server certificate and key
        context.load_cert_chain(
            certfile=str(self.server_cert_path),
            keyfile=str(self.server_key_path)
        )
        
        # Load CA certificate for client verification
        context.load_verify_locations(str(self.ca_cert_path))
        
        # Require agent certificates (mutual TLS)
        context.verify_mode = ssl.CERT_REQUIRED
        
        # Use strong ciphers only
        context.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS')
        
        return context
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter
    ):
        """Handle new client connection."""
        addr = writer.get_extra_info('peername')
        
        self.stats["total_connections"] += 1
        self.stats["active_connections"] += 1
        
        # Create handler
        handler = ClientHandler(
            reader,
            writer,
            self.db,
            self.nonce_cache,
            self.event_queue,
            self.notifiers,
            addr
        )
        
        # Handle connection
        try:
            await handler.handle()
        finally:
            self.stats["active_connections"] -= 1
    
    async def start(self):
        """Start the server."""
        logger.info("=" * 60)
        logger.info("HoneyGrid Server Starting")
        logger.info("=" * 60)
        
        # Create SSL context
        ssl_context = self._create_ssl_context()
        logger.info(f"✓ TLS context created (mutual authentication required)")
        
        # Start server
        self.server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            ssl=ssl_context
        )
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"✓ Server listening on {addr[0]}:{addr[1]}")
        logger.info(f"✓ Database: {self.db.db_path}")
        logger.info(f"✓ Nonce cache size: {self.nonce_cache.max_size}")
        logger.info(f"✓ Agent timeout: {self.agent_timeout}s")
        logger.info("="* 60)
        
        # Start health monitoring task
        self.health_monitor_task = asyncio.create_task(self._check_agent_health())
        logger.info("✓ Agent health monitor started")
        
        # Serve forever
        async with self.server:
            await self.server.serve_forever()
    
    def stop(self):
        """Stop the server."""
        logger.info("Stopping server...")
        
        # Stop health monitor
        if self.health_monitor_task:
            self.health_monitor_task.cancel()
        
        if self.server:
            self.server.close()
        
        # Close database
        self.db.close()
        
        logger.info("✓ Server stopped")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        db_stats = self.db.get_stats()
        return {
            **self.stats,
            **db_stats,
            "nonce_cache_size": self.nonce_cache.size()
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="HoneyGrid Server")
    parser.add_argument("--host", default=None, help="Bind address")
    parser.add_argument("--port", type=int, default=None, help="Bind port")
    parser.add_argument("--db", default=None, help="Database path")
    parser.add_argument("--db-password", default=None, help="Database password")
    
    args = parser.parse_args()

    # Load configuration (YAML + env overrides)
    # Try to load config.yaml first, fall back to defaults
    config = load_config("server/config.yaml", DEFAULT_SERVER_CONFIG)

    # Resolve settings with CLI overrides
    host = args.host or get_nested_value(config, "server.host", "0.0.0.0")
    port = args.port or get_nested_value(config, "server.port", 9000)
    db_path = args.db or get_nested_value(config, "server.database.path", "data/honeygrid.db")
    db_password = args.db_password or get_nested_value(
        config,
        "server.database.password",
        "change_this_password"
    )
    
    # Create server
    server = HoneyGridServer(
        host=host,
        port=port,
        db_path=db_path,
        db_password=db_password,
        config=config
    )
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    finally:
        server.stop()
        
        # Show statistics
        stats = server.get_stats()
        logger.info("\n" + "=" * 60)
        logger.info("Server Statistics:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
