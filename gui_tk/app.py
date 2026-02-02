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
import socket
import subprocess
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.env_loader import load_env

from server.db import DatabaseManager
from gui_tk.map_frame import MapFrame
from gui_tk.alert_frame import AlertFrame
from gui_tk.stats_frame import StatsFrame
from gui_tk.deploy_dialog import show_deploy_dialog
from gui_tk.theme import get_theme_manager, apply_theme_to_widget

# Load environment variables from .env if available
load_env()


class HoneyGridApp:
    """
    Main HoneyGrid dashboard application.
    """

    def __init__(
        self,
        db_path: str = "data/honeygrid.db",
        db_password: str = "change_this_password",
        server_queue: queue.Queue = None,
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

        # Theme manager
        self.theme_manager = get_theme_manager()
        self.current_theme = self.theme_manager.get_theme()

        # Main window
        self.root = tk.Tk()
        self.root.title("HoneyGrid Dashboard")
        self.root.geometry("1200x700")

        # Apply initial theme to window
        self.root.config(bg=self.current_theme["bg"])

        # Set window icon (if available)
        try:
            self.root.iconbitmap("assets/icon.ico")
        except:
            pass
        try:
            icon_path = Path("assets") / "honeygrid.png"
            if icon_path.exists():
                icon_image = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, icon_image)
                self._icon_image = icon_image
        except:
            pass

        # Style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self._apply_ttk_theme()

        # Components
        self.map_frame = None
        self.alert_frame = None
        self.stats_frame = None

        # State
        self.is_running = False
        self.update_thread = None
        self.server_process = None

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
        file_menu.add_command(label="Reset Database", command=self._reset_database)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Refresh Agents", command=self._refresh_agents)
        view_menu.add_command(label="Clear Alerts", command=self._clear_alerts)
        view_menu.add_separator()
        # Add theme toggle menu item first
        view_menu.add_command(label="Toggle Dark Mode", command=self._toggle_theme)
        # Store reference to theme toggle menu item for dynamic label updates
        self.theme_menu_item = view_menu
        self.theme_menu_index = view_menu.index("end")
        self._update_theme_menu_label()

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
            self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Register for theme changes
        self.theme_manager.register_callback(self._on_theme_change)

        # Main container with PanedWindow
        # Server warning banner (hidden by default)
        self.server_banner = ttk.Label(
            self.root,
            text="⚠️  Server not running - start the server to receive events",
            background="#fff3cd",
            foreground="#856404",
            padding=6,
            anchor=tk.CENTER,
        )
        self.server_banner.pack(fill=tk.X, padx=5, pady=(5, 0))
        self.server_banner.pack_forget()

        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left panel - Network Map
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)

        ttk.Label(left_frame, text="Network Map", font=("Arial", 12, "bold")).pack(
            pady=5
        )

        self.map_frame = MapFrame(left_frame, self.db)
        self.map_frame.pack(fill=tk.BOTH, expand=True)

        # Right panel - Tabbed notebook for Alerts and Stats
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

        # Create notebook (tabs)
        notebook = ttk.Notebook(right_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Alert tab
        alert_tab = ttk.Frame(notebook)
        notebook.add(alert_tab, text="Alerts")

        self.alert_frame = AlertFrame(alert_tab, self.db)
        self.alert_frame.pack(fill=tk.BOTH, expand=True)

        # Stats tab
        stats_tab = ttk.Frame(notebook)
        notebook.add(stats_tab, text="Statistics")

        self.stats_frame = StatsFrame(stats_tab, self.db)
        self.stats_frame.pack(fill=tk.BOTH, expand=True)

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
            if self.stats_frame:
                self.stats_frame.set_database(self.db)

            self._set_status("Connected to database")
        except Exception as e:
            messagebox.showerror(
                "Database Error", f"Failed to connect to database:\n{e}"
            )

    def _start_update_loop(self):
        """Start background update loop."""
        self.is_running = True
        self.update_thread = threading.Thread(target=self._update_worker, daemon=True)
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
        self._update_server_status()
        if self.map_frame:
            self.map_frame.refresh()
        if self.alert_frame:
            self.alert_frame.refresh()
        if self.stats_frame:
            self.stats_frame.refresh()

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
        if not self.db:
            messagebox.showerror("Error", "Database not connected")
            return

        result = show_deploy_dialog(self.root, self.db, self._on_token_deployed)

        if result:
            # Refresh displays
            self._refresh_data()

    def _on_token_deployed(self, deployment_info: dict):
        """Callback when token is deployed."""
        print(
            f"Token deployed: {deployment_info['token_id']} to {deployment_info['agent_id']}"
        )
        # Additional handling can be added here (e.g., send notification to agent)

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
            "Coventry University",
        )

    def _reset_database(self):
        """Reset entire database after confirmation."""
        if not self.db:
            messagebox.showerror("Error", "Database not connected")
            return

        # Confirm action
        result = messagebox.askyesno(
            "Reset Database",
            "⚠️  This will delete ALL events, agents, and tokens.\n\n"
            "This action cannot be undone!\n\n"
            "Are you sure?",
            icon=messagebox.WARNING,
        )

        if not result:
            return

        try:
            # Stop server before resetting database
            if not self._stop_server_if_running():
                return

            # Close current connection
            try:
                self.db.close()
            except Exception:
                pass

            # Delete database file
            import os

            try:
                if os.path.exists(self.db_path):
                    os.remove(self.db_path)
                    self._set_status("Database deleted")
            except Exception as e:
                # Reconnect so the UI keeps working
                self.db = DatabaseManager(self.db_path, self.db_password)
                self.db.connect()
                if self.map_frame:
                    self.map_frame.set_database(self.db)
                if self.alert_frame:
                    self.alert_frame.set_database(self.db)
                if self.stats_frame:
                    self.stats_frame.set_database(self.db)
                self._refresh_data()

                messagebox.showerror(
                    "Reset Error",
                    "Failed to reset database (file is in use).\n\n"
                    "Please stop the server before resetting the database.\n\n"
                    f"Details: {e}",
                )
                self._set_status("Database reset failed")
                return

            # Reconnect and reinitialize
            self.db = DatabaseManager(self.db_path, self.db_password)
            self.db.connect()

            # Update all frames with new database
            if self.map_frame:
                self.map_frame.set_database(self.db)
            if self.alert_frame:
                self.alert_frame.set_database(self.db)
            if self.stats_frame:
                self.stats_frame.set_database(self.db)

            # Refresh displays
            self._refresh_data()

            messagebox.showinfo(
                "Database Reset",
                "✓ Database has been reset successfully!\n\n"
                "All events, agents, and tokens have been cleared.",
            )
            self._set_status("Database reset complete")

            # Restart server after reset
            self._restart_server_after_reset()

        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset database:\n{e}")
            self._set_status("Database reset failed")

    def _stop_server_if_running(self) -> bool:
        """Stop the HoneyGrid server if running. Returns False if server can't be stopped."""
        if not self._is_server_running():
            return True

        # If this GUI started the server, terminate it
        if self.server_process and self.server_process.poll() is None:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                return True
            except Exception as e:
                messagebox.showerror(
                    "Server Stop Error", f"Failed to stop server process:\n{e}"
                )
                return False

        # Server is running but not owned by this GUI
        result = messagebox.askyesno(
            "Server Stop Required",
            "Server is running in another process.\n\n" "Do you want to stop it now?",
        )
        if not result:
            return False

        try:
            subprocess.run(
                [
                    "powershell",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    "Get-CimInstance Win32_Process | "
                    "Where-Object { $_.CommandLine -match 'server\\server.py' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1)
        except Exception as e:
            messagebox.showerror("Server Stop Error", f"Failed to stop server:\n{e}")
            return False

        if self._is_server_running():
            messagebox.showerror(
                "Server Stop Error",
                "Server is still running.\n\n"
                "Please stop it manually, then retry the reset.",
            )
            return False

        return True

    def _restart_server_after_reset(self):
        """Restart the server after database reset."""
        restart_script = Path("restart_server.ps1")
        if restart_script.exists():
            try:
                subprocess.run(
                    [
                        "powershell",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(restart_script),
                        "-DbPath",
                        self.db_path,
                        "-DbPassword",
                        self.db_password,
                        "-Host",
                        "0.0.0.0",
                        "-Port",
                        "9000",
                        "-PythonPath",
                        sys.executable,
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._set_status("Server restarted")
                return
            except Exception as e:
                messagebox.showerror(
                    "Server Restart Error", f"Failed to restart server:\n{e}"
                )
                self._set_status("Server restart failed")
                return

        # Fallback to direct start if script not found
        self._ensure_server_running()

    def _ensure_server_running(self):
        """Ensure the HoneyGrid server is running, start it if needed."""
        if self._is_server_running():
            return

        try:
            args = [
                sys.executable,
                "server/server.py",
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--db",
                self.db_path,
                "--db-password",
                self.db_password,
            ]
            self.server_process = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._set_status("Server restarted")
        except Exception as e:
            messagebox.showerror(
                "Server Restart Error", f"Failed to restart server:\n{e}"
            )
            self._set_status("Server restart failed")

    def _is_server_running(self) -> bool:
        """Check if server is listening on localhost:9000."""
        try:
            with socket.create_connection(("127.0.0.1", 9000), timeout=0.5):
                return True
        except OSError:
            return False

    def _set_status(self, message: str):
        """Update status bar."""
        self.status_bar.config(text=message)

    def _update_server_status(self):
        """Update server status banner and status bar hint."""
        if self._is_server_running():
            if self.server_banner.winfo_ismapped():
                self.server_banner.pack_forget()
            # Only overwrite status if it's a server warning
            if self.status_bar.cget("text").startswith("⚠️ Server"):
                self._set_status("Ready")
        else:
            if not self.server_banner.winfo_ismapped():
                self.server_banner.pack(fill=tk.X, padx=5, pady=(5, 0))
            self._set_status("⚠️ Server not running")

    def _apply_ttk_theme(self):
        """Apply theme to ttk widgets."""
        theme = self.current_theme
        
        # Configure ttk styles
        style = self.style
        
        # Background and foreground colors
        bg = theme.get("frame_bg", theme["bg"])
        fg = theme.get("label_fg", theme["fg"])
        tree_bg = theme.get("tree_bg", bg)
        tree_fg = theme.get("tree_fg", fg)
        tree_field_bg = theme.get("tree_field_bg", tree_bg)
        tree_field_fg = theme.get("tree_field_fg", tree_fg)
        button_bg = theme.get("button_bg", bg)
        
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TButton", background=button_bg, foreground=fg)
        style.map("TButton", background=[('active', theme.get("highlight", "#0078d4"))])
        style.configure("TEntry", background=tree_field_bg, foreground=tree_field_fg, 
                       insertcolor=tree_field_fg, fieldbackground=tree_field_bg)
        style.map("TEntry", foreground=[('focus', tree_field_fg)])
        
        # Treeview styling - more comprehensive
        style.configure("Treeview", 
                       background=tree_bg, 
                       foreground=tree_fg,
                       fieldbackground=tree_field_bg,
                       borderwidth=0)
        style.configure("Treeview.Heading", 
                       background=tree_field_bg, 
                       foreground=tree_fg,
                       borderwidth=1)
        style.map("Treeview.Heading",
                 background=[('active', theme.get("highlight", "#0078d4"))])
        
        style.configure("TNotebook", background=bg)
        style.configure("TNotebook.Tab", background=bg, foreground=fg)
        style.map("TNotebook.Tab", 
                 background=[('selected', bg), ('active', button_bg)])
        style.configure("TMenubutton", background=bg, foreground=fg)

    def _update_theme_menu_label(self):
        """Update theme toggle menu item label based on current theme."""
        if self.theme_manager.is_dark_mode():
            label = "Toggle Light Mode"
        else:
            label = "Toggle Dark Mode"
        self.theme_menu_item.entryconfig(self.theme_menu_index, label=label)

    def _toggle_theme(self):
        """Toggle between light and dark theme."""
        self.theme_manager.toggle_theme()

    def _on_theme_change(self, new_theme):
        """Handle theme change."""
        try:
            self.current_theme = new_theme
            
            # Update main window
            self.root.config(bg=new_theme["bg"])
            
            # Update status bar
            try:
                self.status_bar.config(bg=new_theme.get("statusbar_bg", new_theme["bg"]), 
                                      fg=new_theme.get("statusbar_fg", new_theme["fg"]))
            except tk.TclError:
                pass  # Widget might not exist yet
            
            # Update server banner
            try:
                warning_bg = new_theme.get("warning_bg", "#fff3cd")
                warning_fg = new_theme.get("warning_fg", "#856404")
                self.server_banner.config(background=warning_bg, foreground=warning_fg)
            except tk.TclError:
                pass  # Widget might not exist yet
            
            # Reapply ttk theme
            self._apply_ttk_theme()
            
            # Update all frames (ttk.Frame uses style, not direct config)
            # Just refresh the frames to redraw with new styling
            if self.map_frame and self.map_frame.winfo_exists():
                try:
                    self.map_frame.refresh()
                except Exception:
                    pass
            if self.alert_frame and self.alert_frame.winfo_exists():
                try:
                    self.alert_frame.refresh()
                except Exception:
                    pass
            if self.stats_frame and self.stats_frame.winfo_exists():
                try:
                    self.stats_frame.refresh()
                except Exception:
                    pass
            
            # Update menu label
            self._update_theme_menu_label()
            
            self._set_status(f"Theme changed to {self.theme_manager.current_theme.upper()}")
        except Exception as e:
            print(f"Error in theme change callback: {e}")

    def _set_status(self, message: str):
        """Update status bar."""
        self.status_bar.config(text=message)

    def _update_server_status(self):
        """Update server status banner and status bar hint."""
        if self._is_server_running():
            if self.server_banner.winfo_ismapped():
                self.server_banner.pack_forget()
            # Only overwrite status if it's a server warning
            if self.status_bar.cget("text").startswith("⚠️ Server"):
                self._set_status("Ready")
        else:
            if not self.server_banner.winfo_ismapped():
                self.server_banner.pack(fill=tk.X, padx=5, pady=(5, 0))
            self._set_status("⚠️ Server not running")

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
        "--db-password", default="change_this_password", help="Database password"
    )

    args = parser.parse_args()

    # Create and run application
    app = HoneyGridApp(db_path=args.db, db_password=args.db_password)
    app.run()


if __name__ == "__main__":
    main()
