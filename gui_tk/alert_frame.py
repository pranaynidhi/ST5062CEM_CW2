#!/usr/bin/env python3
"""
HoneyGrid Alert Frame
List of honeytoken events with details and export functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import time
import csv
from typing import List, Dict, Optional


class AlertFrame(ttk.Frame):
    """
    Alert panel showing recent honeytoken events.
    """
    
    def __init__(self, parent, db=None):
        """
        Initialize alert frame.
        
        Args:
            parent: Parent widget
            db: Database manager
        """
        super().__init__(parent)
        
        self.db = db
        self.events = []
        
        # Build UI
        self._build_ui()
        
        # Initial refresh
        if self.db:
            self.refresh()
    
    def _build_ui(self):
        """Build user interface."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            toolbar,
            text="Refresh",
            command=self.refresh
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="Export CSV",
            command=self._export_csv
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            toolbar,
            text="Clear",
            command=self.clear
        ).pack(side=tk.LEFT, padx=2)
        
        # Event count label
        self.count_label = ttk.Label(toolbar, text="Events: 0")
        self.count_label.pack(side=tk.RIGHT, padx=5)
        
        # Treeview for events
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        # Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("time", "agent", "token", "type", "path"),
            show="headings",
            yscrollcommand=vsb.set,
            xscrollcommand=hsb.set
        )
        
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        # Column headings
        self.tree.heading("time", text="Time")
        self.tree.heading("agent", text="Agent")
        self.tree.heading("token", text="Token")
        self.tree.heading("type", text="Type")
        self.tree.heading("path", text="Path")
        
        # Column widths
        self.tree.column("time", width=150)
        self.tree.column("agent", width=100)
        self.tree.column("token", width=120)
        self.tree.column("type", width=80)
        self.tree.column("path", width=300)
        
        # Layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Bind double-click
        self.tree.bind("<Double-1>", self._on_double_click)
        
        # Tag configuration for colors
        self.tree.tag_configure("warning", background="#fff3cd")
        self.tree.tag_configure("danger", background="#f8d7da")
    
    def set_database(self, db):
        """Set database connection."""
        self.db = db
        self.refresh()
    
    def refresh(self):
        """Refresh events from database."""
        if not self.db:
            return
        
        try:
            # Get recent events
            self.events = self.db.get_recent_events(limit=100)
            
            # Update treeview
            self._populate_tree()
            
            # Update count
            self.count_label.config(text=f"Events: {len(self.events)}")
        
        except Exception as e:
            print(f"Failed to refresh events: {e}")
    
    def _populate_tree(self):
        """Populate treeview with events."""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add events (most recent first)
        for event in self.events:
            # Format timestamp
            timestamp = event.get('timestamp', 0)
            time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            
            # Get data
            agent_id = event.get('agent_id', 'Unknown')
            token_id = event.get('token_id', 'Unknown')
            event_type = event.get('event_type', 'Unknown')
            path = event.get('path', 'Unknown')
            
            # Determine tag based on event type
            tag = "danger" if event_type in ["opened", "modified"] else "warning"
            
            # Insert row
            self.tree.insert(
                "",
                "end",
                values=(time_str, agent_id, token_id, event_type, path),
                tags=(tag,)
            )
    
    def clear(self):
        """Clear event list."""
        self.events = []
        self._populate_tree()
        self.count_label.config(text="Events: 0")
    
    def _on_double_click(self, event):
        """Handle double-click on event."""
        selection = self.tree.selection()
        if not selection:
            return
        
        # Get item index
        item = selection[0]
        item_index = self.tree.index(item)
        
        if item_index >= len(self.events):
            return
        
        # Get event data
        event_data = self.events[item_index]
        
        # Show details dialog
        self._show_event_details(event_data)
    
    def _show_event_details(self, event: Dict):
        """
        Show event details dialog.
        
        Args:
            event: Event data
        """
        # Create dialog
        dialog = tk.Toplevel(self)
        dialog.title("Event Details")
        dialog.geometry("500x400")
        dialog.transient(self)
        dialog.grab_set()
        
        # Create text widget with scrollbar
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        text = tk.Text(frame, wrap=tk.WORD, width=60, height=20)
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        text.config(yscrollcommand=scrollbar.set)
        
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Format event details
        timestamp = event.get('timestamp', 0)
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
        
        details = f"""Event Details
{'=' * 50}

Event ID: {event.get('id', 'N/A')}
Time: {time_str}
Agent ID: {event.get('agent_id', 'Unknown')}
Token ID: {event.get('token_id', 'Unknown')}
Event Type: {event.get('event_type', 'Unknown')}
Path: {event.get('path', 'Unknown')}

Nonce: {event.get('nonce', 'N/A')}

Additional Data:
{'-' * 50}
"""
        
        # Add additional data
        data = event.get('data', {})
        if data:
            for key, value in data.items():
                details += f"{key}: {value}\n"
        else:
            details += "(No additional data)\n"
        
        # Insert text
        text.insert("1.0", details)
        text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(
            dialog,
            text="Close",
            command=dialog.destroy
        ).pack(pady=5)
    
    def _export_csv(self):
        """Export events to CSV file."""
        if not self.events:
            messagebox.showinfo("Export", "No events to export")
            return
        
        # Ask for filename
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export Events to CSV"
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    "Timestamp",
                    "Agent ID",
                    "Token ID",
                    "Event Type",
                    "Path",
                    "Nonce"
                ])
                
                # Write events
                for event in self.events:
                    timestamp = event.get('timestamp', 0)
                    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
                    
                    writer.writerow([
                        time_str,
                        event.get('agent_id', ''),
                        event.get('token_id', ''),
                        event.get('event_type', ''),
                        event.get('path', ''),
                        event.get('nonce', '')
                    ])
            
            messagebox.showinfo("Export", f"Exported {len(self.events)} events to:\n{filename}")
        
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export:\n{e}")


if __name__ == "__main__":
    # Test the alert frame
    root = tk.Tk()
    root.title("Alert Frame Test")
    root.geometry("800x400")
    
    frame = AlertFrame(root)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Add test events
    frame.events = [
        {
            "id": 1,
            "timestamp": time.time(),
            "agent_id": "agent-001",
            "token_id": "token-abc123",
            "event_type": "opened",
            "path": "C:\\honeytokens\\secret.docx",
            "nonce": "test_nonce_001"
        },
        {
            "id": 2,
            "timestamp": time.time() - 3600,
            "agent_id": "agent-002",
            "token_id": "token-def456",
            "event_type": "modified",
            "path": "C:\\honeytokens\\passwords.txt",
            "nonce": "test_nonce_002"
        }
    ]
    frame._populate_tree()
    frame.count_label.config(text=f"Events: {len(frame.events)}")
    
    root.mainloop()
