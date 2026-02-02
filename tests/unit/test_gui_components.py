#!/usr/bin/env python3
"""
Unit Tests for GUI Components
Tests AlertFrame search/filter, StatsFrame, and MapFrame health status.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import tkinter as tk
import tempfile
import time
from unittest.mock import Mock, MagicMock

from server.db import DatabaseManager
from gui_tk.alert_frame import AlertFrame
from gui_tk.stats_frame import StatsFrame
from gui_tk.map_frame import MapFrame


@pytest.fixture
def root():
    """Create a root window for testing."""
    root = tk.Tk()
    yield root
    root.destroy()


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DatabaseManager(temp_file.name, "test")
    db.connect()
    
    # Add test data
    db.register_agent("agent-001", "host-1", "192.168.1.100")
    db.register_agent("agent-002", "host-2", "192.168.1.101")
    
    for i in range(10):
        db.insert_event(
            agent_id=f"agent-00{(i % 2) + 1}",
            token_id=f"token-{(i % 3) + 1:03d}",
            path=f"C:\\test\\file{i}.txt",
            event_type=["created", "modified", "opened", "deleted"][i % 4],
            nonce=f"nonce-{i:03d}"
        )
    
    yield db
    
    db.close()
    import os
    os.unlink(temp_file.name)


class TestAlertFrame:
    """Test AlertFrame with search/filter functionality."""
    
    def test_init(self, root, test_db):
        """Test AlertFrame initialization."""
        frame = AlertFrame(root, test_db)
        
        assert frame.db == test_db
        assert hasattr(frame, 'search_vars')
        assert hasattr(frame, 'filtered_events')
        assert len(frame.search_vars) == 4  # agent, token, type, path
    
    def test_refresh_loads_events(self, root, test_db):
        """Test that refresh loads events from database."""
        frame = AlertFrame(root, test_db)
        frame.refresh()
        
        assert len(frame.events) > 0
        assert len(frame.filtered_events) > 0
    
    def test_filter_by_agent(self, root, test_db):
        """Test filtering events by agent ID."""
        frame = AlertFrame(root, test_db)
        frame.refresh()
        
        # Set filter
        frame.search_vars['agent'].set('agent-001')
        frame.apply_filter()
        
        # All filtered events should be from agent-001
        for event in frame.filtered_events:
            assert 'agent-001' in event.get('agent_id', '')
    
    def test_filter_by_event_type(self, root, test_db):
        """Test filtering events by event type."""
        frame = AlertFrame(root, test_db)
        frame.refresh()
        
        # Set filter
        frame.search_vars['type'].set('opened')
        frame.apply_filter()
        
        # All filtered events should be 'opened' type
        for event in frame.filtered_events:
            assert 'opened' in event.get('event_type', '').lower()
    
    def test_clear_filter(self, root, test_db):
        """Test clearing all filters."""
        frame = AlertFrame(root, test_db)
        frame.refresh()
        
        # Set some filters
        frame.search_vars['agent'].set('agent-001')
        frame.search_vars['type'].set('opened')
        frame.apply_filter()
        
        original_count = len(frame.filtered_events)
        
        # Clear filters
        frame.clear_filter()
        
        # Should have all events now
        assert len(frame.filtered_events) >= original_count
        assert frame.search_vars['agent'].get() == ''
        assert frame.search_vars['type'].get() == ''
    
    def test_multiple_filters(self, root, test_db):
        """Test applying multiple filters simultaneously."""
        frame = AlertFrame(root, test_db)
        frame.refresh()
        
        # Set multiple filters
        frame.search_vars['agent'].set('agent-001')
        frame.search_vars['type'].set('modified')
        frame.apply_filter()
        
        # All filtered events should match both criteria
        for event in frame.filtered_events:
            assert 'agent-001' in event.get('agent_id', '')
            assert 'modified' in event.get('event_type', '').lower()


class TestStatsFrame:
    """Test StatsFrame statistics display."""
    
    def test_init(self, root, test_db):
        """Test StatsFrame initialization."""
        frame = StatsFrame(root, test_db)
        
        assert frame.db == test_db
        assert hasattr(frame, 'overview_labels')
        assert hasattr(frame, 'agent_listbox')
        assert hasattr(frame, 'type_listbox')
        assert hasattr(frame, 'token_listbox')
    
    def test_refresh_updates_stats(self, root, test_db):
        """Test that refresh updates statistics."""
        frame = StatsFrame(root, test_db)
        frame.refresh()
        
        # Check that overview labels have values
        total_events = frame.overview_labels['total_events'].cget('text')
        assert total_events != '0'
        
        total_agents = frame.overview_labels['total_agents'].cget('text')
        assert total_agents != '0'
    
    def test_agent_listbox_populated(self, root, test_db):
        """Test that agent listbox is populated."""
        frame = StatsFrame(root, test_db)
        frame.refresh()
        
        # Agent listbox should have entries
        assert frame.agent_listbox.size() > 0
    
    def test_type_listbox_populated(self, root, test_db):
        """Test that event type listbox is populated."""
        frame = StatsFrame(root, test_db)
        frame.refresh()
        
        # Type listbox should have entries
        assert frame.type_listbox.size() > 0


class TestMapFrame:
    """Test MapFrame network visualization with health status."""
    
    def test_init(self, root, test_db):
        """Test MapFrame initialization."""
        frame = MapFrame(root, test_db)
        
        assert frame.db == test_db
        assert hasattr(frame, 'agents')
        assert hasattr(frame, 'colors')
        assert 'healthy' in frame.colors
        assert 'warning' in frame.colors
        assert 'offline' in frame.colors
    
    def test_refresh_loads_agents(self, root, test_db):
        """Test that refresh loads agents from database."""
        frame = MapFrame(root, test_db)
        frame.refresh()
        
        assert len(frame.agents) > 0
    
    def test_update_agent_status(self, root, test_db):
        """Test updating individual agent status."""
        frame = MapFrame(root, test_db)
        frame.refresh()
        
        # Update status
        frame.update_agent_status('agent-001', 'warning')
        
        # Check that status was updated
        assert frame.agents['agent-001']['status'] == 'warning'
    
    def test_status_colors(self, root):
        """Test that status colors are defined."""
        frame = MapFrame(root)
        
        assert frame.colors['healthy'] == '#2ecc71'  # Green
        assert frame.colors['warning'] == '#f39c12'  # Orange
        assert frame.colors['triggered'] == '#e74c3c'  # Red
        assert frame.colors['offline'] == '#95a5a6'  # Gray


class TestHealthMonitoring:
    """Test health monitoring integration."""
    
    def test_agent_status_update(self, test_db):
        """Test that agent status can be updated."""
        # Update agent status
        test_db.update_agent_status('agent-001', 'warning')
        
        # Retrieve agent
        agent = test_db.get_agent('agent-001')
        
        assert agent['status'] == 'warning'
    
    def test_timeout_detection_logic(self, test_db):
        """Test timeout detection logic."""
        current_time = int(time.time())
        agent_timeout = 90
        
        # Simulate old agent
        cursor = test_db.connection.cursor()
        cursor.execute(
            "UPDATE agents SET last_seen = ? WHERE agent_id = ?",
            (current_time - 100, 'agent-001')
        )
        test_db.connection.commit()
        
        # Get agent
        agent = test_db.get_agent('agent-001')
        last_seen = agent.get('last_seen', 0)
        time_since_seen = current_time - last_seen
        
        # Should be marked for timeout
        assert time_since_seen > agent_timeout


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
