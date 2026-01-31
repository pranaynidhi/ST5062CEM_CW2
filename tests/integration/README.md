# Integration Tests

## Overview
End-to-end integration tests for HoneyGrid, testing complete workflows across components.

## Test Files

### test_server_agent.py
Tests server-agent communication with real TLS connections:
- **TestServerAgentCommunication** (5 tests):
  - Server accepts client connections
  - Agent sends events to server
  - Multiple events transmission
  - Replay attack prevention
  - Connection statistics tracking
- **TestServerStatistics** (1 test):
  - Multiple concurrent connections

**What's tested:**
- TLS mutual authentication (CA, server cert, client cert)
- Message framing and parsing
- Database event storage
- Nonce-based replay protection
- Rate limiting
- Multiprocessing server/client

### test_file_monitor.py
Tests file system monitoring with real file operations:
- **TestFileMonitoring** (6 tests):
  - File creation detection
  - File modification detection
  - File deletion detection
  - File move/rename detection
  - Multiple watch paths with different token IDs
  - Directory vs file distinction
- **TestMonitorPerformance** (1 test):
  - Rapid file changes handling

**What's tested:**
- Watchdog file system observer
- Event queue communication
- Token ID mapping
- File vs directory events
- Multiple simultaneous watches

## Running Integration Tests

### Prerequisites
1. SSL certificates must be generated:
   ```bash
   python scripts\generate_certs.py
   ```

2. Ensure test ports are available (19000 by default)

### Run all integration tests:
```bash
python -m pytest tests\integration\ -v -s
```

### Run specific test file:
```bash
python -m pytest tests\integration\test_server_agent.py -v -s
```

### Run specific test:
```bash
python -m pytest tests\integration\test_server_agent.py::TestServerAgentCommunication::test_agent_sends_event -v -s
```

### Run with coverage:
```bash
python -m pytest tests\integration\ --cov=server --cov=agent --cov-report=term-missing
```

## Important Notes

### Timeouts
Integration tests use real processes and I/O, so they include sleep delays:
- Server startup: 1-2 seconds
- Event processing: 1-2 seconds
- File system events: 1-3 seconds

Tests may fail if system is under heavy load. Increase timeouts if needed.

### Process Management
Tests spawn multiprocessing.Process instances for server. They're cleaned up with:
- `process.terminate()` - graceful shutdown
- `process.kill()` - force kill if timeout
- Always run in try/finally blocks

### Port Conflicts
Tests use port 19000 (not 9000) to avoid conflicts with running server.
Change TEST_PORT in test files if needed.

### File System Events
File monitoring tests create temporary directories and files. They're automatically cleaned up after tests.

On Windows, file system events may be slightly delayed. Tests account for this with sleep delays.

## Troubleshooting

### Server fails to start
- Check certificates exist in certs/ directory
- Ensure port 19000 is not in use
- Check firewall settings

### Events not detected
- Increase sleep times in tests
- Check watchdog is properly installed
- Verify temp directories have write permissions

### Process cleanup issues
- Check Task Manager for orphaned python.exe processes
- Kill manually if needed: `taskkill /F /IM python.exe /T`

### Database locked errors
- Ensure previous test closed database properly
- Check for leftover temp files in TEMP directory

## Coverage Goals

Integration tests complement unit tests to achieve:
- **Server components**: ~80% coverage
- **Agent components**: ~70% coverage
- **End-to-end workflows**: Full critical paths tested

Combined with unit tests, targeting >80% overall coverage.
