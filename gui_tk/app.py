#!/usr/bin/env python3
"""
HoneyGrid GUI Application
Main tkinter dashboard for monitoring honeytokens and agents.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.db import DatabaseManager
from map_frame import MapFrame
from alert_frame import AlertFrame


class HoneyGridApp:
    """
    Main HoneyGrid dashboard application.
    """
    
    def __init__(
        self,
        db_path: str = "data/honeygrid.db",
        db_password: str = "change_this_password",
        server_queue: queue.Queue = None
    ):
        """
        Initialize GUI application.
        
        Args:
            db_path: Database file path
            db_password: Database encryption password
            server_queue: Queue for receiving events from server
        """
        self.db_path = db_path
        self.db_password = db_password
        self.server_queue = server_queue or queue.Queue()
        
        # Database connection
        self.db = None
        
        # Main window
        self.root = tk.Tk()
        self.root.title("HoneyGrid Dashboard")
        self.root.geometry("1200x700")
        
        # Set window icon (if available)
        try:
            self.root.iconbitmap("assets/icon.ico")
        except:
            pass
        
        # Style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Components
        self.map_frame = None
        self.alert_frame = None
        
        # State
        self.is_running = False
        self.update_thread = None
        
        # Build UI
        self._build_ui()
        
        # Connect to database
        self._connect_database()
        
        # Start update loop
        self._start_update_loop()
    
    def _build_ui(self):
        """Build the user interface."""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh Data", command=self._refresh_data)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh Agents", command=self._refresh_agents)
        view_menu.add_command(label="Clear Alerts", command=self._clear_alerts)
        
        # Actions menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions_menu)
        actions_menu.add_command(label="Deploy Token", command=self._deploy_token)
        actions_menu.add_command(label="Database Statistics", command=self._show_stats)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)
        
        # Status bar
        self.status_bar = ttk.Label(
            self.root,
            text="Ready",
            relief=tk.SUNKEN,
            anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Main container with PanedWindow
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Left panel - Network Map
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        
        ttk.Label(
            left_frame,
            text="Network Map",
            font=("Arial", 12, "bold")
        ).pack(pady=5)
        
        self.map_frame = MapFrame(left_frame, self.db)
        self.map_frame.pack(fill=tk.BOTH, expand=True)
        
        # Right panel - Alert List
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        
        ttk.Label(
            right_frame,
            text="Alert Panel",
            font=("Arial", 12, "bold")
        ).pack(pady=5)
        
        self.alert_frame = AlertFrame(right_frame, self.db)
        self.alert_frame.pack(fill=tk.BOTH, expand=True)
    
    def _connect_database(self):
        """Connect to database."""
        try:
            self.db = DatabaseManager(self.db_path, self.db_password)
            self.db.connect()
            
            # Pass database to frames
            if self.map_frame:
                self.map_frame.set_database(self.db)
            if self.alert_frame:
                self.alert_frame.set_database(self.db)
            
            self._set_status("Connected to database")
        except Exception as e:
            messagebox.showerror(
                "Database Error",
                f"Failed to connect to database:\n{e}"
            )
    
    def _start_update_loop(self):
        """Start background update loop."""
        self.is_running = True
        self.update_thread = threading.Thread(
            target=self._update_worker,
            daemon=True
        )
        self.update_thread.start()
    
    def _update_worker(self):
        """Background worker for processing updates."""
        while self.is_running:
            try:
                # Check for new events from server
                try:
                    event = self.server_queue.get(timeout=1.0)
                    self._process_server_event(event)
                except queue.Empty:
                    pass
                
                # Periodic refresh (every 5 seconds)
                time.sleep(5)
                self.root.after(0, self._periodic_refresh)
            
            except Exception as e:
                print(f"Update worker error: {e}")
    
    def _process_server_event(self, event: dict):
        """
        Process event from server.
        
        Args:
            event: Event dictionary from server
        """
        # Update UI on main thread
        self.root.after(0, lambda: self._handle_new_event(event))
    
    def _handle_new_event(self, event: dict):
        """Handle new event (on main thread)."""
        event_type = event.get("type")
        
        if event_type == "event":
            # New honeytoken trigger
            agent_id = event.get("agent_id")
            
            # Update map (agent status to red)
            if self.map_frame:
                self.map_frame.update_agent_status(agent_id, "triggered")
            
            # Add to alert list
            if self.alert_frame:
                self.alert_frame.refresh()
            
            # Show notification
            self._set_status(f"🚨 ALERT: Honeytoken triggered by {agent_id}")
            
            # Flash window to get attention
            self.root.bell()
    
    def _periodic_refresh(self):
        """Periodic refresh of data."""
        if self.map_frame:
            self.map_frame.refresh()
        if self.alert_frame:
            self.alert_frame.refresh()
    
    def _refresh_data(self):
        """Refresh all data."""
        self._set_status("Refreshing data...")
        self._periodic_refresh()
        self._set_status("Data refreshed")
    
    def _refresh_agents(self):
        """Refresh agent map."""
        if self.map_frame:
            self.map_frame.refresh()
        self._set_status("Agents refreshed")
    
    def _clear_alerts(self):
        """Clear alert list."""
        if self.alert_frame:
            self.alert_frame.clear()
        self._set_status("Alerts cleared")
    
    def _deploy_token(self):
        """Show deploy token dialog."""
        messagebox.showinfo(
            "Deploy Token",
            "Token deployment dialog not yet implemented.\n"
            "Use agent CLI to deploy tokens."
        )
    
    def _show_stats(self):
        """Show database statistics."""
        if not self.db:
            return
        
        try:
            stats = self.db.get_stats()
            
            message = (
                f"Database Statistics:\n\n"
                f"Total Agents: {stats['total_agents']}\n"
                f"Total Events: {stats['total_events']}\n"
                f"Total Tokens: {stats['total_tokens']}\n"
                f"Events (24h): {stats['events_24h']}\n"
                f"DB Size: {stats['db_size_bytes'] / 1024:.1f} KB"
            )
            
            messagebox.showinfo("Database Statistics", message)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get statistics:\n{e}")
    
    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About HoneyGrid",
            "HoneyGrid v1.0\n\n"
            "GUI-Driven Distributed Honeytoken\n"
            "Deployment & Monitor\n\n"
            "ST5062CEM Coursework 2\n"
            "Coventry University"
        )
    
    def _set_status(self, message: str):
        """Update status bar."""
        self.status_bar.config(text=message)
    
    def _on_close(self):
        """Handle window close."""
        self.is_running = False
        
        if self.update_thread and self.update_thread.is_alive():
            self.update_thread.join(timeout=2)
        
        if self.db:
            self.db.close()
        
        self.root.destroy()
    
    def run(self):
        """Run the application."""
        # Set close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Start main loop
        self.root.mainloop()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="HoneyGrid Dashboard")
    parser.add_argument("--db", default="data/honeygrid.db", help="Database path")
    parser.add_argument(
        "--db-password",
        default="change_this_password",
        help="Database password"
    )
    
    args = parser.parse_args()
    
    # Create and run application
    app = HoneyGridApp(
        db_path=args.db,
        db_password=args.db_password
    )
    app.run()


if __name__ == "__main__":
    main()
