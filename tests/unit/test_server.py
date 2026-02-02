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
        self.notifiers = []
        self.addr = ("127.0.0.1", 12345)
    
    def test_init_without_cert(self):
        """Test ClientHandler initialization without agent certificate."""
        # Mock writer to return no SSL info
        self.writer.get_extra_info.return_value = None
        
        handler = ClientHandler(
            self.reader,
            self.writer,
            self.db,
            self.nonce_cache,
            self.event_queue,
            self.notifiers,
            self.addr
        )
        
        self.assertIsNotNone(handler.agent_id)
        self.assertIn("unknown", handler.agent_id)
        self.assertFalse(handler.is_authenticated)
        self.assertEqual(handler.message_count, 0)
    
    def test_init_with_cert(self):
        """Test ClientHandler initialization with agent certificate."""
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
            self.notifiers,
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
            self.notifiers,
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
            self.notifiers,
            self.addr
        )
        
        self.assertEqual(handler.message_count, 0)


class TestLRUCacheEdgeCases:
    """Test LRU cache edge cases."""
    
    def test_empty_cache_size(self):
        """Test empty cache size."""
        cache = LRUCache(max_size=10)
        assert cache.size() == 0
    
    def test_cache_with_max_size_one(self):
        """Test cache with max_size=1."""
        cache = LRUCache(max_size=1)
        cache.add("item1")
        assert cache.contains("item1")
        cache.add("item2")
        assert cache.contains("item2")
        assert not cache.contains("item1")
    
    def test_add_same_item_multiple_times(self):
        """Test adding same item multiple times doesn't grow cache."""
        cache = LRUCache(max_size=10)
        for _ in range(5):
            cache.add("same_item")
        assert cache.size() == 1
    
    def test_cache_ordering(self):
        """Test cache maintains LRU ordering."""
        cache = LRUCache(max_size=5)
        for i in range(5):
            cache.add(f"item{i}")
        
        # Access item0 (moves to end)
        cache.add("item0")
        
        # Add new item, should evict item1
        cache.add("item5")
        assert not cache.contains("item1")
        assert cache.contains("item0")


class TestClientHandlerProperties:
    """Test ClientHandler properties and attributes."""
    
    def test_handler_has_reader(self):
        """Test handler has reader attribute."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert hasattr(handler, 'reader')
    
    def test_handler_has_writer(self):
        """Test handler has writer attribute."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert hasattr(handler, 'writer')
    
    def test_handler_has_db(self):
        """Test handler has db attribute."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert hasattr(handler, 'db')
    
    def test_handler_has_nonce_cache(self):
        """Test handler has nonce_cache attribute."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert hasattr(handler, 'nonce_cache')
    
    def test_handler_has_event_queue(self):
        """Test handler has event_queue attribute."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert hasattr(handler, 'event_queue')
    
    def test_handler_has_addr(self):
        """Test handler has addr attribute."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        addr = ("192.168.1.100", 9000)
        
        handler = ClientHandler(
            reader, writer, Mock(), LRUCache(), Queue(), [], addr
        )
        assert handler.addr == addr
    
    def test_handler_is_authenticated_false(self):
        """Test handler is_authenticated starts as False."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.get_extra_info.return_value = None
        
        handler = ClientHandler(
            reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert handler.is_authenticated is False


class TestClientHandlerWithDifferentCerts:
    """Test ClientHandler with different certificate scenarios."""
    
    def test_handler_with_valid_cert_common_name(self):
        """Test handler extracts CommonName from certificate."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        
        mock_ssl = Mock()
        mock_ssl.getpeercert.return_value = {
            'subject': ((('commonName', 'test-agent-001'),),)
        }
        writer.get_extra_info.return_value = mock_ssl
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert handler.agent_id == "test-agent-001"
    
    def test_handler_with_no_common_name(self):
        """Test handler with cert but no CommonName."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        
        mock_ssl = Mock()
        mock_ssl.getpeercert.return_value = {
            'subject': ((('organizationName', 'Test Org'),),)
        }
        writer.get_extra_info.return_value = mock_ssl
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("127.0.0.1", 12345)
        )
        assert handler.agent_id == "unknown"
    
    def test_handler_with_no_peer_cert(self):
        """Test handler with SSL but no peer certificate."""
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        
        mock_ssl = Mock()
        mock_ssl.getpeercert.return_value = None
        writer.get_extra_info.return_value = mock_ssl
        
        handler = ClientHandler(reader, writer, Mock(), LRUCache(), Queue(), [], ("10.0.0.1", 8443)
        )
        assert "unknown_10.0.0.1_8443" == handler.agent_id


class TestLRUCacheBehavior:
    """Test LRU cache specific behaviors."""
    
    def test_recently_used_items_stay(self):
        """Test recently used items aren't evicted."""
        cache = LRUCache(max_size=3)
        cache.add("A")
        cache.add("B")
        cache.add("C")
        
        # Use A again
        cache.add("A")
        
        # Add D, should evict B
        cache.add("D")
        
        assert cache.contains("A")
        assert not cache.contains("B")
        assert cache.contains("C")
        assert cache.contains("D")
    
    def test_cache_max_size_property(self):
        """Test cache max_size is set correctly."""
        for size in [10, 100, 1000, 5000]:
            cache = LRUCache(max_size=size)
            assert cache.max_size == size


if __name__ == '__main__':
    unittest.main()


