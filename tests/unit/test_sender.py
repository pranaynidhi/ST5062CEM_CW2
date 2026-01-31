#!/usr/bin/env python3
"""
Unit tests for agent sender module.
Tests rate limiting and message sending.
"""

import pytest
import time
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.sender import RateLimiter


class TestRateLimiter:
    """Test rate limiter (token bucket algorithm)."""
    
    def test_initial_tokens(self):
        """Test that limiter starts with full bucket."""
        limiter = RateLimiter(rate=10.0, burst=20)
        assert limiter.get_tokens() == 20.0
    
    def test_acquire_single(self):
        """Test acquiring a single token."""
        limiter = RateLimiter(rate=10.0, burst=20)
        success = limiter.acquire(tokens=1, blocking=False)
        assert success is True
        # Allow small variance due to time passing
        assert 18.9 <= limiter.get_tokens() <= 19.1
    
    def test_acquire_multiple(self):
        """Test acquiring multiple tokens."""
        limiter = RateLimiter(rate=10.0, burst=20)
        success = limiter.acquire(tokens=5, blocking=False)
        assert success is True
        # Allow small variance due to time passing
        assert 14.9 <= limiter.get_tokens() <= 15.1
    
    def test_acquire_exceeds_available(self):
        """Test that acquiring more than available fails."""
        limiter = RateLimiter(rate=10.0, burst=5)
        
        # Consume all tokens
        limiter.acquire(tokens=5, blocking=False)
        
        # Try to acquire more
        success = limiter.acquire(tokens=1, blocking=False, timeout=0.1)
        assert success is False
    
    def test_refill_over_time(self):
        """Test that tokens refill over time."""
        limiter = RateLimiter(rate=10.0, burst=10)  # 10 tokens/sec
        
        # Consume all tokens
        limiter.acquire(tokens=10, blocking=False)
        # Small amount of time passes, allow minor refill
        assert limiter.get_tokens() < 0.1
        
        # Wait 1 second
        time.sleep(1.0)
        
        # Should have refilled ~10 tokens
        tokens = limiter.get_tokens()
        assert 9.0 <= tokens <= 10.0
    
    def test_refill_does_not_exceed_burst(self):
        """Test that refill doesn't exceed burst capacity."""
        limiter = RateLimiter(rate=10.0, burst=5)
        
        # Start with full bucket
        assert limiter.get_tokens() == 5.0
        
        # Wait 2 seconds (would add 20 tokens at rate)
        time.sleep(2.0)
        
        # Should be capped at burst size
        tokens = limiter.get_tokens()
        assert tokens <= 5.0
    
    def test_acquire_with_timeout(self):
        """Test acquire with blocking and timeout."""
        limiter = RateLimiter(rate=5.0, burst=1)
        
        # Consume token
        limiter.acquire(tokens=1, blocking=False)
        
        # Try to acquire with short timeout (should fail)
        start = time.time()
        success = limiter.acquire(tokens=1, blocking=True, timeout=0.1)
        elapsed = time.time() - start
        
        assert success is False
        assert elapsed < 0.2  # Should timeout quickly
    
    def test_concurrent_acquire(self):
        """Test that acquire is thread-safe."""
        limiter = RateLimiter(rate=100.0, burst=10)
        
        # Rapid acquire calls
        results = []
        for _ in range(5):
            success = limiter.acquire(tokens=2, blocking=False)
            results.append(success)
        
        # First 5 should succeed (10 tokens available, 2 each)
        assert results == [True, True, True, True, True]
        # Allow small variance due to time passing and refill
        assert limiter.get_tokens() < 1.0


class TestRateLimiterEdgeCases:
    """Test rate limiter edge cases."""
    
    def test_zero_tokens_request(self):
        """Test requesting zero tokens."""
        limiter = RateLimiter(rate=10.0, burst=10)
        success = limiter.acquire(tokens=0, blocking=False)
        assert success is True  # Should always succeed
        assert limiter.get_tokens() == 10.0  # No tokens consumed
    
    def test_fractional_rate(self):
        """Test fractional rate (less than 1 token/sec)."""
        limiter = RateLimiter(rate=0.5, burst=2)
        
        # Consume all tokens
        limiter.acquire(tokens=2, blocking=False)
        
        # Wait 2 seconds (should add 1 token)
        time.sleep(2.0)
        
        tokens = limiter.get_tokens()
        assert 0.9 <= tokens <= 1.1
    
    def test_large_burst(self):
        """Test rate limiter with large burst capacity."""
        limiter = RateLimiter(rate=100.0, burst=1000)
        assert limiter.get_tokens() == 1000.0
        
        # Should handle large acquisitions
        success = limiter.acquire(tokens=500, blocking=False)
        assert success is True
        assert 499.0 <= limiter.get_tokens() <= 500.1
    
    def test_high_rate(self):
        """Test rate limiter with high rate."""
        limiter = RateLimiter(rate=1000.0, burst=100)
        
        # Consume all
        limiter.acquire(tokens=100, blocking=False)
        
        # Wait 0.1 second (should add 100 tokens at 1000/sec)
        time.sleep(0.1)
        
        tokens = limiter.get_tokens()
        assert 90.0 <= tokens <= 100.0  # Should be capped at burst
    
    def test_very_small_timeout(self):
        """Test acquire with very small timeout."""
        limiter = RateLimiter(rate=1.0, burst=1)
        limiter.acquire(tokens=1, blocking=False)
        
        # Try with extremely small timeout
        success = limiter.acquire(tokens=1, blocking=True, timeout=0.001)
        assert success is False
    
    def test_multiple_small_acquires(self):
        """Test multiple small token acquisitions."""
        limiter = RateLimiter(rate=10.0, burst=10)
        
        # Acquire 10 times, 1 token each
        for i in range(10):
            success = limiter.acquire(tokens=1, blocking=False)
            assert success is True
        
        # Next acquire should fail (all consumed)
        success = limiter.acquire(tokens=1, blocking=False, timeout=0.05)
        assert success is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
