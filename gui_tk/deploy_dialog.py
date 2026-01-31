#!/usr/bin/env python3
"""
Token Deployment Dialog for HoneyGrid GUI.
Allows user to deploy honeytokens to agents with configuration options.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import List, Dict, Optional, Callable
import os
from datetime import datetime
from pathlib import Path


class DeployDialog:
    """
    Dialog for deploying honeytokens to agents.
    """
    
    def __init__(self, parent, db_manager, on_deploy_callback: Optional[Callable] = None):
        """
        Initialize deployment dialog.
        
        Args:
            parent: Parent tk widget
            db_manager: DatabaseManager instance
            on_deploy_callback: Callback function when deployment is confirmed
        """
        self.db = db_manager
        self.on_deploy_callback = on_deploy_callback
        self.result = None
        
        # Create top-level window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Deploy Honeytoken")
        self.dialog.geometry("600x650")
        self.dialog.resizable(False, False)
        
        # Make dialog modal
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center dialog
        self.dialog.update_idletasks()
        x = (parent.winfo_screenwidth() // 2) - (600 // 2)
        y = (parent.winfo_screenheight() // 2) - (650 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self._build_ui()
        self._load_agents()
    
    def _build_ui(self):
        """Build dialog UI."""
        # Main container with padding
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Deploy Honeytoken",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Token Information Section
        token_frame = ttk.LabelFrame(main_frame, text="Token Information", padding="10")
        token_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Token ID
        ttk.Label(token_frame, text="Token ID:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.token_id_var = tk.StringVar(value=f"token-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        token_id_entry = ttk.Entry(token_frame, textvariable=self.token_id_var, width=40)
        token_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Token Name
        ttk.Label(token_frame, text="Token Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.token_name_var = tk.StringVar(value="Secret Document")
        token_name_entry = ttk.Entry(token_frame, textvariable=self.token_name_var, width=40)
        token_name_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Token Type
        ttk.Label(token_frame, text="Token Type:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.token_type_var = tk.StringVar(value="document")
        token_type_combo = ttk.Combobox(
            token_frame,
            textvariable=self.token_type_var,
            values=["document", "image", "spreadsheet", "database", "script", "other"],
            state="readonly",
            width=37
        )
        token_type_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Token Path
        ttk.Label(token_frame, text="File Path:").grid(row=3, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(token_frame)
        path_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        self.token_path_var = tk.StringVar(value="C:\\honeytokens\\secret.docx")
        token_path_entry = ttk.Entry(path_frame, textvariable=self.token_path_var)
        token_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        browse_btn = ttk.Button(path_frame, text="Browse...", command=self._browse_file, width=10)
        browse_btn.pack(side=tk.LEFT, padx=(5, 0))
        
        token_frame.columnconfigure(1, weight=1)
        
        # Agent Selection Section
        agent_frame = ttk.LabelFrame(main_frame, text="Target Agent", padding="10")
        agent_frame.pack(fill=tk.BOTH, pady=(0, 10))
        
        # Agent list
        list_frame = ttk.Frame(agent_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox
        self.agent_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            selectmode=tk.SINGLE,
            height=8
        )
        self.agent_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.agent_listbox.yview)
        
        # Agent info label
        self.agent_info_label = ttk.Label(
            agent_frame,
            text="Select an agent from the list above",
            foreground="gray"
        )
        self.agent_info_label.pack(pady=(5, 0))
        
        # Bind selection event
        self.agent_listbox.bind('<<ListboxSelect>>', self._on_agent_select)
        
        # Deployment Options Section
        options_frame = ttk.LabelFrame(main_frame, text="Deployment Options", padding="10")
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Auto-monitor option
        self.auto_monitor_var = tk.BooleanVar(value=True)
        auto_monitor_check = ttk.Checkbutton(
            options_frame,
            text="Automatically monitor this file",
            variable=self.auto_monitor_var
        )
        auto_monitor_check.pack(anchor=tk.W)
        
        # Alert on access option
        self.alert_on_access_var = tk.BooleanVar(value=True)
        alert_check = ttk.Checkbutton(
            options_frame,
            text="Generate alert on any access",
            variable=self.alert_on_access_var
        )
        alert_check.pack(anchor=tk.W)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            width=15
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 5))
        
        deploy_btn = ttk.Button(
            button_frame,
            text="Deploy",
            command=self._deploy,
            width=15
        )
        deploy_btn.pack(side=tk.RIGHT)
    
    def _load_agents(self):
        """Load available agents from database."""
        try:
            agents = self.db.get_all_agents()
            
            if not agents:
                self.agent_listbox.insert(tk.END, "No agents available")
                self.agent_listbox.config(state=tk.DISABLED)
                return
            
            # Add online/healthy agents first
            for agent in sorted(agents, key=lambda a: (a['status'] != 'healthy', a['agent_id'])):
                status_icon = "●" if agent['status'] == 'healthy' else "○"
                display_text = f"{status_icon} {agent['agent_id']} - {agent['hostname']} ({agent['status']})"
                self.agent_listbox.insert(tk.END, display_text)
                
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to load agents: {str(e)}",
                parent=self.dialog
            )
    
    def _on_agent_select(self, event):
        """Handle agent selection."""
        selection = self.agent_listbox.curselection()
        if selection:
            selected_text = self.agent_listbox.get(selection[0])
            if "No agents available" in selected_text:
                return
            
            # Extract agent_id from display text
            agent_id = selected_text.split(" - ")[0].replace("● ", "").replace("○ ", "").strip()
            
            # Show agent info
            try:
                agent = self.db.get_agent(agent_id)
                if agent:
                    info_text = f"📍 {agent['hostname']} | 🌐 {agent['ip_address']} | Status: {agent['status'].upper()}"
                    self.agent_info_label.config(text=info_text, foreground="black")
            except:
                pass
    
    def _browse_file(self):
        """Open file browser for token path."""
        initial_dir = os.path.dirname(self.token_path_var.get()) or "C:\\"
        
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Select honeytoken file path",
            initialdir=initial_dir,
            initialfile=os.path.basename(self.token_path_var.get())
        )
        
        if filename:
            self.token_path_var.set(filename)
    
    def _validate_inputs(self) -> bool:
        """Validate user inputs."""
        # Check token ID
        if not self.token_id_var.get().strip():
            messagebox.showerror(
                "Validation Error",
                "Token ID is required",
                parent=self.dialog
            )
            return False
        
        # Check token name
        if not self.token_name_var.get().strip():
            messagebox.showerror(
                "Validation Error",
                "Token name is required",
                parent=self.dialog
            )
            return False
        
        # Check file path
        if not self.token_path_var.get().strip():
            messagebox.showerror(
                "Validation Error",
                "File path is required",
                parent=self.dialog
            )
            return False
        
        # Check agent selection
        selection = self.agent_listbox.curselection()
        if not selection:
            messagebox.showerror(
                "Validation Error",
                "Please select a target agent",
                parent=self.dialog
            )
            return False
        
        selected_text = self.agent_listbox.get(selection[0])
        if "No agents available" in selected_text:
            messagebox.showerror(
                "Validation Error",
                "No agents available for deployment",
                parent=self.dialog
            )
            return False
        
        return True
    
    def _deploy(self):
        """Handle deploy button click."""
        if not self._validate_inputs():
            return
        
        # Extract agent_id from selection
        selection = self.agent_listbox.curselection()
        selected_text = self.agent_listbox.get(selection[0])
        agent_id = selected_text.split(" - ")[0].replace("● ", "").replace("○ ", "").strip()
        
        # Build result dictionary
        self.result = {
            'token_id': self.token_id_var.get().strip(),
            'name': self.token_name_var.get().strip(),
            'type': self.token_type_var.get(),
            'path': self.token_path_var.get().strip(),
            'agent_id': agent_id,
            'auto_monitor': self.auto_monitor_var.get(),
            'alert_on_access': self.alert_on_access_var.get(),
            'deployed_at': datetime.now().isoformat()
        }
        
        # Register token in database
        try:
            self.db.register_token(
                token_id=self.result['token_id'],
                name=self.result['name'],
                path=self.result['path'],
                deployed_to=agent_id,
                metadata={
                    'type': self.result['type'],
                    'auto_monitor': self.result['auto_monitor'],
                    'alert_on_access': self.result['alert_on_access']
                }
            )
            
            # Show success message
            messagebox.showinfo(
                "Deployment Successful",
                f"Token '{self.result['name']}' has been registered for deployment to {agent_id}.\n\n"
                f"Note: You need to manually configure the agent to monitor this file path:\n"
                f"{self.result['path']}",
                parent=self.dialog
            )
            
            # Call callback if provided
            if self.on_deploy_callback:
                self.on_deploy_callback(self.result)
            
            # Close dialog
            self.dialog.destroy()
            
        except Exception as e:
            messagebox.showerror(
                "Deployment Error",
                f"Failed to register token: {str(e)}",
                parent=self.dialog
            )
    
    def _cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
    
    def show(self) -> Optional[Dict]:
        """
        Show dialog and wait for user action.
        
        Returns:
            Dictionary with deployment info if deployed, None if cancelled
        """
        self.dialog.wait_window()
        return self.result


def show_deploy_dialog(parent, db_manager, on_deploy_callback=None) -> Optional[Dict]:
    """
    Show token deployment dialog.
    
    Args:
        parent: Parent tk widget
        db_manager: DatabaseManager instance
        on_deploy_callback: Optional callback function
    
    Returns:
        Deployment info dict if deployed, None if cancelled
    """
    dialog = DeployDialog(parent, db_manager, on_deploy_callback)
    return dialog.show()


if __name__ == "__main__":
    # Test dialog
    root = tk.Tk()
    root.withdraw()
    
    # Create temporary database
    import tempfile
    import sys
    from pathlib import Path
    
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from server.db import DatabaseManager
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DatabaseManager(temp_file.name, "test")
    db.connect()
    
    # Add test agents
    db.register_agent("agent-001", "test-host-1", "192.168.1.100")
    db.register_agent("agent-002", "test-host-2", "192.168.1.101")
    db.update_agent_status("agent-001", "healthy")
    db.update_agent_status("agent-002", "warning")
    
    # Show dialog
    result = show_deploy_dialog(root, db)
    
    if result:
        print("Deployment:", result)
    else:
        print("Cancelled")
    
    # Cleanup
    db.close()
    import os
    os.unlink(temp_file.name)
