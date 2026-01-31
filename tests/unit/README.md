# Unit Tests - Summary

## Overview

Comprehensive unit tests for HoneyGrid core components.

## Test Coverage

### test_protocol.py (23 tests)

Tests the message protocol implementation:

- **Nonce Generation** (3 tests): Length, uniqueness, base64 encoding
- **MessageHeader** (7 tests): Creation, serialization, validation (nonce, timestamp, msg_type)
- **Message** (5 tests): Message creation, event/heartbeat helpers, serialization
- **Framing** (5 tests): Frame message, parse roundtrip, invalid JSON/structure
- **Validation** (3 tests): Valid messages, invalid nonce, timestamp tolerance

### test_db.py (15 tests)

Tests the encrypted database layer:

- **Connection** (2 tests): Connect, table creation
- **Encryption** (2 tests): Encrypt/decrypt, uniqueness
- **Agent Management** (4 tests): Register, status update, get all, nonexistent
- **Event Management** (4 tests): Insert, replay protection (duplicate nonce), recent events, filter by agent
- **Token Management** (2 tests): Register token, nonexistent token
- **Statistics** (1 test): Database stats

### test_sender.py (10 tests)

Tests the rate limiter (token bucket):

- **Basic Operations** (7 tests): Initial tokens, single/multiple acquire, exceeds available, refill over time, burst cap, blocking with timeout, concurrent acquire
- **Edge Cases** (3 tests): Zero tokens request, fractional rate, thread safety

## Running Tests

### Run all unit tests

```bash
python -m pytest tests/unit/ -v
```

### Run with coverage

```bash
python -m pytest tests/unit/ --cov=server --cov=agent --cov-report=term-missing
```

### Run specific test file

```bash
python -m pytest tests/unit/test_protocol.py -v
```

### Run specific test

```bash
python -m pytest tests/unit/test_protocol.py::TestNonceGeneration::test_nonce_length -v
```

### Use test runner script

```bash
python run_tests.py
```

## Test Results

### Total: 48 tests

- ✅ test_protocol.py: 23/23 passed
- ✅ test_db.py: 15/15 passed
- ✅ test_sender.py: 10/10 passed

**Coverage:**

- server/protocol.py: ~59%
- server/db.py: ~73%
- agent/sender.py: ~28% (RateLimiter class fully tested)

## Notes

- Tests use temporary files/databases (pytest fixtures with cleanup)
- Rate limiter tests allow small time variance due to token refill
- Database tests verify encryption, replay protection, and data integrity
- Protocol tests validate message structure, framing, and timestamp checks
