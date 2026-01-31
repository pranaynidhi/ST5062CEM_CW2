#!/usr/bin/env python3
"""
HoneyGrid Network Map Frame
Canvas-based visualization of agents and their status.
"""

import tkinter as tk
from tkinter import ttk
import math
from typing import Dict, List, Optional


class MapFrame(ttk.Frame):
    """
    Network map showing agent nodes with status colors.
    """
    
    def __init__(self, parent, db=None):
        """
        Initialize map frame.
        
        Args:
            parent: Parent widget
            db: Database manager
        """
        super().__init__(parent)
        
        self.db = db
        self.agents = {}  # agent_id -> agent_data
        self.node_positions = {}  # agent_id -> (x, y)
        self.node_ids = {}  # agent_id -> canvas_id
        
        # Create canvas
        self.canvas = tk.Canvas(self, bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind resize
        self.canvas.bind("<Configure>", self._on_resize)
        
        # Colors
        self.colors = {
            "healthy": "#2ecc71",  # Green
            "warning": "#f39c12",  # Orange
            "triggered": "#e74c3c",  # Red
            "offline": "#95a5a6"  # Gray
        }
        
        # Initial refresh
        if self.db:
            self.refresh()
    
    def set_database(self, db):
        """Set database connection."""
        self.db = db
        self.refresh()
    
    def refresh(self):
        """Refresh agents from database."""
        if not self.db:
            return
        
        try:
            # Get all agents
            agents = self.db.get_all_agents()
            
            # Update agent data
            self.agents = {agent['agent_id']: agent for agent in agents}
            
            # Redraw
            self._draw_network()
        
        except Exception as e:
            print(f"Failed to refresh agents: {e}")
    
    def update_agent_status(self, agent_id: str, status: str):
        """
        Update agent status.
        
        Args:
            agent_id: Agent identifier
            status: New status
        """
        if agent_id in self.agents:
            self.agents[agent_id]['status'] = status
            self._update_node(agent_id)
    
    def _on_resize(self, event):
        """Handle canvas resize."""
        self._draw_network()
    
    def _draw_network(self):
        """Draw network map."""
        # Clear canvas
        self.canvas.delete("all")
        
        if not self.agents:
            # Show "No agents" message
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height()
            self.canvas.create_text(
                width // 2,
                height // 2,
                text="No agents connected",
                fill="#7f8c8d",
                font=("Arial", 14)
            )
            return
        
        # Calculate node positions
        self._calculate_positions()
        
        # Draw nodes
        for agent_id, agent in self.agents.items():
            self._draw_node(agent_id, agent)
    
    def _calculate_positions(self):
        """Calculate node positions in a circle layout."""
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        if width <= 1 or height <= 1:
            width, height = 600, 400
        
        center_x = width // 2
        center_y = height // 2
        radius = min(width, height) // 3
        
        num_agents = len(self.agents)
        
        if num_agents == 1:
            # Single agent in center
            agent_id = list(self.agents.keys())[0]
            self.node_positions[agent_id] = (center_x, center_y)
        else:
            # Circular layout
            angle_step = 2 * math.pi / num_agents
            
            for i, agent_id in enumerate(self.agents.keys()):
                angle = i * angle_step
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                self.node_positions[agent_id] = (x, y)
    
    def _draw_node(self, agent_id: str, agent: Dict):
        """
        Draw agent node.
        
        Args:
            agent_id: Agent identifier
            agent: Agent data
        """
        if agent_id not in self.node_positions:
            return
        
        x, y = self.node_positions[agent_id]
        
        # Node size
        radius = 40
        
        # Get status color
        status = agent.get('status', 'offline')
        color = self.colors.get(status, self.colors['offline'])
        
        # Draw circle
        node_id = self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=color,
            outline="#ecf0f1",
            width=2
        )
        
        # Draw agent ID text
        self.canvas.create_text(
            x,
            y,
            text=agent_id,
            fill="white",
            font=("Arial", 10, "bold")
        )
        
        # Draw status text below
        status_text = status.upper()
        self.canvas.create_text(
            x,
            y + radius + 15,
            text=status_text,
            fill=color,
            font=("Arial", 8)
        )
        
        # Store canvas ID
        self.node_ids[agent_id] = node_id
        
        # Bind click event
        self.canvas.tag_bind(node_id, "<Button-1>", lambda e: self._on_node_click(agent_id))
    
    def _update_node(self, agent_id: str):
        """Update existing node appearance."""
        if agent_id not in self.node_ids:
            # Node doesn't exist, redraw everything
            self._draw_network()
            return
        
        # Get position
        if agent_id not in self.node_positions:
            return
        
        x, y = self.node_positions[agent_id]
        radius = 40
        
        # Get new color
        agent = self.agents.get(agent_id, {})
        status = agent.get('status', 'offline')
        color = self.colors.get(status, self.colors['offline'])
        
        # Update node color
        node_id = self.node_ids[agent_id]
        self.canvas.itemconfig(node_id, fill=color)
    
    def _on_node_click(self, agent_id: str):
        """
        Handle node click.
        
        Args:
            agent_id: Clicked agent ID
        """
        agent = self.agents.get(agent_id)
        if not agent:
            return
        
        # Show agent info
        info = (
            f"Agent: {agent_id}\n"
            f"Status: {agent.get('status', 'unknown')}\n"
            f"IP: {agent.get('ip_address', 'N/A')}\n"
            f"Hostname: {agent.get('hostname', 'N/A')}"
        )
        
        # Create tooltip or info window
        print(f"Clicked: {info}")


if __name__ == "__main__":
    # Test the map frame
    root = tk.Tk()
    root.title("Map Frame Test")
    root.geometry("600x400")
    
    frame = MapFrame(root)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Add test agents
    frame.agents = {
        "agent-001": {"agent_id": "agent-001", "status": "healthy", "ip_address": "192.168.1.100"},
        "agent-002": {"agent_id": "agent-002", "status": "warning", "ip_address": "192.168.1.101"},
        "agent-003": {"agent_id": "agent-003", "status": "triggered", "ip_address": "192.168.1.102"},
    }
    frame._draw_network()
    
    root.mainloop()
