#!/usr/bin/env python3
"""
Unit tests for server components (LRUCache, ClientHandler utilities)
"""

import unittest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from queue import Queue
from io import BytesIO

from server.server import LRUCache, ClientHandler


class TestLRUCache(unittest.TestCase):
    """Test LRUCache for nonce replay protection."""
    
    def test_init(self):
        """Test cache initialization."""
        cache = LRUCache(max_size=100)
        self.assertEqual(cache.size(), 0)
        self.assertEqual(cache.max_size, 100)
    
    def test_add_single_item(self):
        """Test adding a single item."""
        cache = LRUCache(max_size=10)
        cache.add("nonce1")
        self.assertEqual(cache.size(), 1)
        self.assertTrue(cache.contains("nonce1"))
    
    def test_add_multiple_items(self):
        """Test adding multiple items."""
        cache = LRUCache(max_size=10)
        for i in range(5):
            cache.add(f"nonce{i}")
        self.assertEqual(cache.size(), 5)
        for i in range(5):
            self.assertTrue(cache.contains(f"nonce{i}"))
    
    def test_add_duplicate_moves_to_end(self):
        """Test that adding duplicate moves it to end (LRU behavior)."""
        cache = LRUCache(max_size=3)
        cache.add("nonce1")
        cache.add("nonce2")
        cache.add("nonce3")
        
        # Re-add nonce1 (should move to end)
        cache.add("nonce1")
        self.assertEqual(cache.size(), 3)
        
        # Add new item, should evict nonce2 (oldest)
        cache.add("nonce4")
        self.assertEqual(cache.size(), 3)
        self.assertFalse(cache.contains("nonce2"))
        self.assertTrue(cache.contains("nonce1"))
        self.assertTrue(cache.contains("nonce3"))
        self.assertTrue(cache.contains("nonce4"))
    
    def test_eviction_when_full(self):
        """Test that oldest items are evicted when cache is full."""
        cache = LRUCache(max_size=3)
        cache.add("nonce1")
        cache.add("nonce2")
        cache.add("nonce3")
        
        # Cache should be full
        self.assertEqual(cache.size(), 3)
        
        # Add one more, should evict nonce1
        cache.add("nonce4")
        self.assertEqual(cache.size(), 3)
        self.assertFalse(cache.contains("nonce1"))
        self.assertTrue(cache.contains("nonce2"))
        self.assertTrue(cache.contains("nonce3"))
        self.assertTrue(cache.contains("nonce4"))
    
    def test_contains_missing_item(self):
        """Test checking for non-existent item."""
        cache = LRUCache(max_size=10)
        cache.add("nonce1")
        self.assertFalse(cache.contains("nonce2"))
    
    def test_large_cache(self):
        """Test cache with many items."""
        cache = LRUCache(max_size=1000)
        
        # Add 1000 items
        for i in range(1000):
            cache.add(f"nonce{i}")
        
        self.assertEqual(cache.size(), 1000)
        
        # All should be present
        for i in range(1000):
            self.assertTrue(cache.contains(f"nonce{i}"))
        
        # Add one more, should evict nonce0
        cache.add("nonce1000")
        self.assertEqual(cache.size(), 1000)
        self.assertFalse(cache.contains("nonce0"))
        self.assertTrue(cache.contains("nonce1000"))


class TestClientHandler(unittest.TestCase):
    """Test ClientHandler initialization and utilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.reader = AsyncMock(spec=asyncio.StreamReader)
        self.writer = MagicMock(spec=asyncio.StreamWriter)
        self.db = Mock()
        self.nonce_cache = LRUCache(max_size=100)
        self.event_queue = Queue()
        self.addr = ("127.0.0.1", 12345)
    
    def test_init_without_cert(self):
        """Test ClientHandler initialization without client certificate."""
        # Mock writer to return no SSL info
        self.writer.get_extra_info.return_value = None
        
        handler = ClientHandler(
            self.reader,
            self.writer,
            self.db,
            self.nonce_cache,
            self.event_queue,
            self.addr
        )
        
        self.assertIsNotNone(handler.agent_id)
        self.assertIn("unknown", handler.agent_id)
        self.assertFalse(handler.is_authenticated)
        self.assertEqual(handler.message_count, 0)
    
    def test_init_with_cert(self):
        """Test ClientHandler initialization with client certificate."""
        # Mock SSL object with certificate
        mock_ssl = Mock()
        mock_ssl.getpeercert.return_value = {
            'subject': ((('commonName', 'agent123'),),)
        }
        self.writer.get_extra_info.return_value = mock_ssl
        
        handler = ClientHandler(
            self.reader,
            self.writer,
            self.db,
            self.nonce_cache,
            self.event_queue,
            self.addr
        )
        
        self.assertEqual(handler.agent_id, "agent123")
        self.assertEqual(handler.addr, self.addr)
        self.assertFalse(handler.is_authenticated)
    
    def test_init_stores_references(self):
        """Test that ClientHandler stores all required references."""
        self.writer.get_extra_info.return_value = None
        
        handler = ClientHandler(
            self.reader,
            self.writer,
            self.db,
            self.nonce_cache,
            self.event_queue,
            self.addr
        )
        
        self.assertIs(handler.reader, self.reader)
        self.assertIs(handler.writer, self.writer)
        self.assertIs(handler.db, self.db)
        self.assertIs(handler.nonce_cache, self.nonce_cache)
        self.assertIs(handler.event_queue, self.event_queue)
    
    def test_message_count_initial(self):
        """Test that message count starts at zero."""
        self.writer.get_extra_info.return_value = None
        
        handler = ClientHandler(
            self.reader,
            self.writer,
            self.db,
            self.nonce_cache,
            self.event_queue,
            self.addr
        )
        
        self.assertEqual(handler.message_count, 0)


if __name__ == '__main__':
    unittest.main()
