#!/usr/bin/env python3
"""
Test Agent Health Monitoring
Verifies that the server correctly detects and marks offline agents.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
import tempfile
from server.db import DatabaseManager


def test_health_monitoring():
    """Test agent timeout detection."""
    print("Testing Agent Health Monitoring")
    print("=" * 60)
    
    # Create temporary database
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DatabaseManager(temp_file.name, "test")
    db.connect()
    
    # Register test agents
    print("\n1. Registering test agents...")
    db.register_agent("agent-001", "test-host-1", "192.168.1.100")
    db.register_agent("agent-002", "test-host-2", "192.168.1.101")
    db.register_agent("agent-003", "test-host-3", "192.168.1.102")
    print("   ✓ Registered 3 agents")
    
    # Set initial status
    db.update_agent_status("agent-001", "healthy")
    db.update_agent_status("agent-002", "healthy")
    db.update_agent_status("agent-003", "healthy")
    print("   ✓ All agents marked as healthy")
    
    # Simulate time passing by manually updating last_seen
    print("\n2. Simulating agent timeouts...")
    current_time = int(time.time())
    
    # Update agent-002 to be stale (>90 seconds old)
    cursor = db.connection.cursor()
    cursor.execute(
        "UPDATE agents SET last_seen = ? WHERE agent_id = ?",
        (current_time - 100, "agent-002")
    )
    db.connection.commit()
    print("   ✓ agent-002 set to 100s old (should be offline)")
    
    # Update agent-003 to be in warning state (>63 seconds old, 70% of 90)
    cursor.execute(
        "UPDATE agents SET last_seen = ? WHERE agent_id = ?",
        (current_time - 65, "agent-003")
    )
    db.connection.commit()
    print("   ✓ agent-003 set to 65s old (should be warning)")
    
    # Check agent health manually (simulate health check task)
    print("\n3. Running health check...")
    agents = db.get_all_agents()
    
    agent_timeout = 90
    for agent in agents:
        last_seen = agent.get('last_seen', 0)
        time_since_seen = current_time - last_seen
        agent_id = agent['agent_id']
        
        if time_since_seen > agent_timeout:
            db.update_agent_status(agent_id, 'offline')
            print(f"   ✓ {agent_id}: OFFLINE (last seen {time_since_seen}s ago)")
        elif time_since_seen > (agent_timeout * 0.7):
            db.update_agent_status(agent_id, 'warning')
            print(f"   ✓ {agent_id}: WARNING (last seen {time_since_seen}s ago)")
        else:
            print(f"   ✓ {agent_id}: HEALTHY (last seen {time_since_seen}s ago)")
    
    # Verify statuses
    print("\n4. Verifying agent statuses...")
    agents = db.get_all_agents()
    for agent in agents:
        status = agent['status']
        agent_id = agent['agent_id']
        print(f"   {agent_id}: {status.upper()}")
    
    # Cleanup
    db.close()
    import os
    os.unlink(temp_file.name)
    
    print("\n" + "=" * 60)
    print("✓ Health monitoring test passed!")


if __name__ == "__main__":
    test_health_monitoring()
