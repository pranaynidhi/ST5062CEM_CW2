#!/usr/bin/env python3
"""
HoneyGrid Database Module
Encrypted SQLite database for storing agents and events.

Uses application-level encryption (Fernet) since pysqlcipher3 requires C++ build tools.
All sensitive data is encrypted before storage.
"""

import sqlite3
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class DatabaseError(Exception):
    """Base exception for database errors."""
    pass


class DatabaseManager:
    """
    Manages encrypted SQLite database for HoneyGrid.
    
    Tables:
        - agents: Registered agents
        - events: Honeytoken access events
        - tokens: Deployed honeytokens
    """
    
    def __init__(self, db_path: str, password: str):
        """
        Initialize database manager.
        
        Args:
            db_path: Path to database file
            password: Encryption password
        """
        self.db_path = Path(db_path)
        self.password = password
        self.connection = None
        self.cipher = None
        
        # Derive encryption key from password
        self._init_encryption()
        
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def _init_encryption(self):
        """Initialize Fernet cipher for data encryption."""
        # Use fixed salt for key derivation (in production, store salt separately)
        salt = b'honeygrid_salt_v1'  # Fixed salt (could be per-database)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.password.encode()))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher.encrypt(data.encode()).decode('ascii')
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        return self.cipher.decrypt(encrypted_data.encode('ascii')).decode()
    
    def connect(self):
        """Connect to database and create tables if needed."""
        if self.connection:
            return
        
        self.connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0
        )
        self.connection.row_factory = sqlite3.Row  # Access columns by name
        
        # Enable foreign keys
        self.connection.execute("PRAGMA foreign_keys = ON")
        
        # Create tables
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        cursor = self.connection.cursor()
        
        # Agents table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                hostname TEXT,
                ip_address TEXT,
                status TEXT DEFAULT 'healthy',
                last_seen INTEGER,
                registered_at INTEGER,
                metadata TEXT
            )
        """)
        
        # Events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                token_id TEXT,
                path TEXT,
                event_type TEXT,
                timestamp INTEGER,
                nonce TEXT UNIQUE,
                data TEXT,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            )
        """)
        
        # Tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token_id TEXT PRIMARY KEY,
                name TEXT,
                path TEXT,
                deployed_to TEXT,
                deployed_at INTEGER,
                status TEXT DEFAULT 'active',
                metadata TEXT
            )
        """)
        
        # Indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_agent 
            ON events(agent_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp 
            ON events(timestamp DESC)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_nonce 
            ON events(nonce)
        """)
        
        self.connection.commit()
    
    def close(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    # Agent Management
    
    def register_agent(
        self,
        agent_id: str,
        hostname: str = None,
        ip_address: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Register a new agent or update existing.
        
        Args:
            agent_id: Unique agent identifier
            hostname: Agent hostname
            ip_address: Agent IP address
            metadata: Additional metadata
        
        Returns:
            True if successful
        """
        cursor = self.connection.cursor()
        timestamp = int(time.time())
        
        metadata_json = json.dumps(metadata or {})
        encrypted_metadata = self.encrypt(metadata_json)
        
        cursor.execute("""
            INSERT INTO agents (agent_id, hostname, ip_address, last_seen, registered_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id) DO UPDATE SET
                hostname = excluded.hostname,
                ip_address = excluded.ip_address,
                last_seen = excluded.last_seen,
                metadata = excluded.metadata
        """, (agent_id, hostname, ip_address, timestamp, timestamp, encrypted_metadata))
        
        self.connection.commit()
        return True
    
    def update_agent_status(self, agent_id: str, status: str) -> bool:
        """
        Update agent status.
        
        Args:
            agent_id: Agent identifier
            status: New status ("healthy", "warning", "error", "offline")
        
        Returns:
            True if successful
        """
        if not self.connection:
            return False
        cursor = self.connection.cursor()
        timestamp = int(time.time())
        
        cursor.execute("""
            UPDATE agents 
            SET status = ?, last_seen = ?
            WHERE agent_id = ?
        """, (status, timestamp, agent_id))
        
        self.connection.commit()
        return cursor.rowcount > 0
    
    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get agent by ID.
        
        Args:
            agent_id: Agent identifier
        
        Returns:
            Agent data or None if not found
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        agent = dict(row)
        if agent['metadata']:
            agent['metadata'] = json.loads(self.decrypt(agent['metadata']))
        
        return agent
    
    def get_all_agents(self) -> List[Dict[str, Any]]:
        """
        Get all registered agents.
        
        Returns:
            List of agent data
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM agents ORDER BY agent_id")
        rows = cursor.fetchall()
        
        agents = []
        for row in rows:
            agent = dict(row)
            if agent['metadata']:
                agent['metadata'] = json.loads(self.decrypt(agent['metadata']))
            agents.append(agent)
        
        return agents
    
    # Event Management
    
    def insert_event(
        self,
        agent_id: str,
        token_id: str,
        path: str,
        event_type: str,
        nonce: str,
        timestamp: int = None,
        data: Dict[str, Any] = None
    ) -> int:
        """
        Insert a new event.
        
        Args:
            agent_id: Agent that reported the event
            token_id: Honeytoken identifier
            path: File path
            event_type: Event type ("opened", "modified", "deleted")
            nonce: Unique nonce for replay protection
            timestamp: Event timestamp (defaults to current time)
            data: Additional event data
        
        Returns:
            Event ID
        
        Raises:
            DatabaseError: If nonce already exists (replay attack)
        """
        if timestamp is None:
            timestamp = int(time.time())
        
        cursor = self.connection.cursor()
        
        # Encrypt sensitive data
        encrypted_path = self.encrypt(path)
        data_json = json.dumps(data or {})
        encrypted_data = self.encrypt(data_json)
        
        try:
            cursor.execute("""
                INSERT INTO events 
                (agent_id, token_id, path, event_type, timestamp, nonce, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent_id, token_id, encrypted_path, event_type, timestamp, nonce, encrypted_data))
            
            self.connection.commit()
            
            # Update agent last_seen
            self.update_agent_status(agent_id, "warning")  # Event = potential breach
            
            return cursor.lastrowid
        
        except sqlite3.IntegrityError as e:
            if "nonce" in str(e):
                raise DatabaseError(f"Duplicate nonce detected: {nonce} (possible replay attack)")
            raise DatabaseError(f"Database integrity error: {e}")
    
    def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        """
        Get event by ID.
        
        Args:
            event_id: Event ID
        
        Returns:
            Event data or None if not found
        """
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return self._decrypt_event(dict(row))
    
    def get_recent_events(self, limit: int = 100, agent_id: str = None) -> List[Dict[str, Any]]:
        """
        Get recent events.
        
        Args:
            limit: Maximum number of events to return
            agent_id: Filter by agent (optional)
        
        Returns:
            List of events (most recent first)
        """
        cursor = self.connection.cursor()
        
        if agent_id:
            cursor.execute("""
                SELECT * FROM events 
                WHERE agent_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (agent_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM events 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        return [self._decrypt_event(dict(row)) for row in rows]
    
    def get_events_by_timerange(
        self,
        start_time: int,
        end_time: int,
        agent_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get events within a time range.
        
        Args:
            start_time: Start timestamp
            end_time: End timestamp
            agent_id: Filter by agent (optional)
        
        Returns:
            List of events
        """
        cursor = self.connection.cursor()
        
        if agent_id:
            cursor.execute("""
                SELECT * FROM events 
                WHERE timestamp >= ? AND timestamp <= ? AND agent_id = ?
                ORDER BY timestamp DESC
            """, (start_time, end_time, agent_id))
        else:
            cursor.execute("""
                SELECT * FROM events 
                WHERE timestamp >= ? AND timestamp <= ?
                ORDER BY timestamp DESC
            """, (start_time, end_time))
        
        rows = cursor.fetchall()
        return [self._decrypt_event(dict(row)) for row in rows]
    
    def _decrypt_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive event fields."""
        if event['path']:
            event['path'] = self.decrypt(event['path'])
        if event['data']:
            event['data'] = json.loads(self.decrypt(event['data']))
        return event
    
    # Token Management
    
    def register_token(
        self,
        token_id: str,
        name: str,
        path: str,
        deployed_to: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Register a deployed honeytoken.
        
        Args:
            token_id: Unique token identifier
            name: Token name/description
            path: File path
            deployed_to: Agent ID where deployed
            metadata: Additional metadata
        
        Returns:
            True if successful
        """
        cursor = self.connection.cursor()
        timestamp = int(time.time())
        
        metadata_json = json.dumps(metadata or {})
        encrypted_metadata = self.encrypt(metadata_json)
        encrypted_path = self.encrypt(path)
        
        cursor.execute("""
            INSERT INTO tokens (token_id, name, path, deployed_to, deployed_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(token_id) DO UPDATE SET
                name = excluded.name,
                path = excluded.path,
                deployed_to = excluded.deployed_to,
                deployed_at = excluded.deployed_at,
                metadata = excluded.metadata
        """, (token_id, name, encrypted_path, deployed_to, timestamp, encrypted_metadata))
        
        self.connection.commit()
        return True
    
    def get_token(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get token by ID."""
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM tokens WHERE token_id = ?", (token_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        token = dict(row)
        if token['path']:
            token['path'] = self.decrypt(token['path'])
        if token['metadata']:
            token['metadata'] = json.loads(self.decrypt(token['metadata']))
        
        return token
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.
        
        Returns:
            Statistics dictionary
        """
        if not self.connection:
            return {"total_agents": 0, "total_events": 0, "total_tokens": 0, "events_24h": 0, "db_size_bytes": 0}
        cursor = self.connection.cursor()
        
        # Count agents
        cursor.execute("SELECT COUNT(*) FROM agents")
        agent_count = cursor.fetchone()[0]
        
        # Count events
        cursor.execute("SELECT COUNT(*) FROM events")
        event_count = cursor.fetchone()[0]
        
        # Count tokens
        cursor.execute("SELECT COUNT(*) FROM tokens")
        token_count = cursor.fetchone()[0]
        
        # Recent events (last 24 hours)
        day_ago = int(time.time()) - 86400
        cursor.execute("SELECT COUNT(*) FROM events WHERE timestamp > ?", (day_ago,))
        recent_events = cursor.fetchone()[0]
        
        return {
            "total_agents": agent_count,
            "total_events": event_count,
            "total_tokens": token_count,
            "events_24h": recent_events,
            "db_size_bytes": os.path.getsize(self.db_path) if self.db_path.exists() else 0
        }


def init_database(db_path: str, password: str):
    """
    Initialize a new database.
    
    Args:
        db_path: Database file path
        password: Encryption password
    """
    print(f"Initializing database: {db_path}")
    
    with DatabaseManager(db_path, password) as db:
        print("✓ Database created successfully")
        print(f"✓ Tables created")
        stats = db.get_stats()
        print(f"✓ Statistics: {stats}")


# Example usage and testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--init":
        # Initialize new database
        db_path = "data/honeygrid.db"
        password = "test_password_change_in_production"
        init_database(db_path, password)
    else:
        # Run tests
        print("HoneyGrid Database Module - Test")
        print("=" * 60)
        
        # Create test database
        test_db = "data/test_honeygrid.db"
        if os.path.exists(test_db):
            os.remove(test_db)
        
        with DatabaseManager(test_db, "test_password") as db:
            # Test 1: Register agents
            print("\n1. Registering agents...")
            db.register_agent("agent-001", "PC-WORKSTATION-1", "192.168.1.100")
            db.register_agent("agent-002", "PC-SERVER-1", "192.168.1.200")
            print(f"   Registered 2 agents")
            
            # Test 2: Insert events
            print("\n2. Inserting events...")
            event_id = db.insert_event(
                agent_id="agent-001",
                token_id="token-abc123",
                path="C:\\honeytokens\\secret.docx",
                event_type="opened",
                nonce="test_nonce_001",
                data={"user": "attacker", "process": "notepad.exe"}
            )
            print(f"   Inserted event ID: {event_id}")
            
            # Test 3: Retrieve events
            print("\n3. Retrieving events...")
            events = db.get_recent_events(limit=10)
            for event in events:
                print(f"   Event {event['id']}: {event['agent_id']} → {event['path']}")
            
            # Test 4: Register token
            print("\n4. Registering token...")
            db.register_token(
                token_id="token-abc123",
                name="Secret Document",
                path="C:\\honeytokens\\secret.docx",
                deployed_to="agent-001"
            )
            print("   Token registered")
            
            # Test 5: Statistics
            print("\n5. Database statistics:")
            stats = db.get_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")
            
            # Test 6: Encryption test
            print("\n6. Encryption test:")
            original = "Sensitive data 123!@#"
            encrypted = db.encrypt(original)
            decrypted = db.decrypt(encrypted)
            print(f"   Original:  {original}")
            print(f"   Encrypted: {encrypted[:50]}...")
            print(f"   Decrypted: {decrypted}")
            print(f"   Match: {original == decrypted}")
        
        print("\n" + "=" * 60)
        print("✓ Database tests passed!")
        print(f"✓ Test database: {test_db}")
