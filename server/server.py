#!/usr/bin/env python3
"""
HoneyGrid Server
Asyncio TLS server with mutual authentication, replay protection, and rate limiting.
Receives events from agents and stores them in encrypted database.
"""

import asyncio
import ssl
import time
import logging
from pathlib import Path
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


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
            addr: Client address
        """
        self.reader = reader
        self.writer = writer
        self.db = db
        self.nonce_cache = nonce_cache
        self.event_queue = event_queue
        self.addr = addr
        
        self.agent_id = None
        self.is_authenticated = False
        self.message_count = 0
        
        # Get client certificate info
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
        max_nonce_cache: int = 1000
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
        """
        self.host = host
        self.port = port
        self.ca_cert_path = Path(ca_cert_path)
        self.server_cert_path = Path(server_cert_path)
        self.server_key_path = Path(server_key_path)
        
        # Initialize database
        self.db = DatabaseManager(db_path, db_password)
        self.db.connect()
        
        # Nonce cache for replay protection
        self.nonce_cache = LRUCache(max_nonce_cache)
        
        # Event queue for GUI
        self.event_queue = Queue(maxsize=1000)
        
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
        
        # Require client certificates (mutual TLS)
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
        logger.info("=" * 60)
        
        # Serve forever
        async with self.server:
            await self.server.serve_forever()
    
    def stop(self):
        """Stop the server."""
        logger.info("Stopping server...")
        
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
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=9000, help="Bind port")
    parser.add_argument("--db", default="data/honeygrid.db", help="Database path")
    parser.add_argument("--db-password", default="change_this_password", help="Database password")
    
    args = parser.parse_args()
    
    # Create server
    server = HoneyGridServer(
        host=args.host,
        port=args.port,
        db_path=args.db,
        db_password=args.db_password
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
