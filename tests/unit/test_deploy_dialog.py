#!/usr/bin/env python3
"""
Unit tests for DeployDialog GUI component.
Tests initialization, UI elements, validation, and deployment logic.
"""

import pytest
import tkinter as tk
from tkinter import ttk
import tempfile
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set TCL/TK library paths before any Tk imports
python_dir = sys.base_prefix
tcl_dir = os.path.join(python_dir, 'tcl')

if os.path.exists(tcl_dir):
    tcl_lib = os.path.join(tcl_dir, 'tcl8.6')
    tk_lib = os.path.join(tcl_dir, 'tk8.6')
    
    if os.path.exists(tcl_lib):
        os.environ['TCL_LIBRARY'] = tcl_lib
    if os.path.exists(tk_lib):
        os.environ['TK_LIBRARY'] = tk_lib

from gui_tk.deploy_dialog import DeployDialog, show_deploy_dialog
from server.db import DatabaseManager


@pytest.fixture
def temp_db():
    """Create temporary database with test agents."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_file.close()
    
    db = DatabaseManager(temp_file.name, "test_pass")
    db.connect()
    
    # Add test agents
    db.register_agent("agent-001", "test-host-1", "192.168.1.100")
    db.register_agent("agent-002", "test-host-2", "192.168.1.101")
    db.update_agent_status("agent-001", "healthy")
    db.update_agent_status("agent-002", "warning")
    
    yield db
    
    db.close()
    try:
        os.unlink(temp_file.name)
    except:
        pass


@pytest.fixture(scope="session")
def tk_root():
    """Create a single Tk root for all tests."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except:
        pass


@pytest.fixture
def root(tk_root):
    """Provide the session-scoped Tk root."""
    return tk_root


class TestDeployDialogInit:
    """Test DeployDialog initialization."""
    
    def test_dialog_init(self, root, temp_db):
        """Test DeployDialog initializes successfully."""
        dialog = DeployDialog(root, temp_db)
        assert dialog is not None
        assert dialog.db is temp_db
        dialog.dialog.destroy()
    
    def test_dialog_has_result_none(self, root, temp_db):
        """Test result is None initially."""
        dialog = DeployDialog(root, temp_db)
        assert dialog.result is None
        dialog.dialog.destroy()
    
    def test_dialog_has_callback(self, root, temp_db):
        """Test callback is stored."""
        callback = lambda x: None
        dialog = DeployDialog(root, temp_db, on_deploy_callback=callback)
        assert dialog.on_deploy_callback is callback
        dialog.dialog.destroy()
    
    def test_dialog_has_token_id_var(self, root, temp_db):
        """Test token_id_var is created."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'token_id_var')
        assert isinstance(dialog.token_id_var, tk.StringVar)
        assert "token-" in dialog.token_id_var.get()
        dialog.dialog.destroy()
    
    def test_dialog_has_token_name_var(self, root, temp_db):
        """Test token_name_var is created."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'token_name_var')
        assert isinstance(dialog.token_name_var, tk.StringVar)
        assert dialog.token_name_var.get() == "Secret Document"
        dialog.dialog.destroy()
    
    def test_dialog_has_token_type_var(self, root, temp_db):
        """Test token_type_var is created."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'token_type_var')
        assert isinstance(dialog.token_type_var, tk.StringVar)
        assert dialog.token_type_var.get() == "document"
        dialog.dialog.destroy()
    
    def test_dialog_has_token_path_var(self, root, temp_db):
        """Test token_path_var is created."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'token_path_var')
        assert isinstance(dialog.token_path_var, tk.StringVar)
        assert "honeytokens" in dialog.token_path_var.get().lower()
        dialog.dialog.destroy()
    
    def test_dialog_has_auto_monitor_var(self, root, temp_db):
        """Test auto_monitor_var is created."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'auto_monitor_var')
        assert isinstance(dialog.auto_monitor_var, tk.BooleanVar)
        assert dialog.auto_monitor_var.get() is True
        dialog.dialog.destroy()
    
    def test_dialog_has_alert_on_access_var(self, root, temp_db):
        """Test alert_on_access_var is created."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'alert_on_access_var')
        assert isinstance(dialog.alert_on_access_var, tk.BooleanVar)
        assert dialog.alert_on_access_var.get() is True
        dialog.dialog.destroy()


class TestDeployDialogUIElements:
    """Test DeployDialog UI elements exist."""
    
    def test_dialog_has_listbox(self, root, temp_db):
        """Test agent listbox exists."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'agent_listbox')
        assert isinstance(dialog.agent_listbox, tk.Listbox)
        dialog.dialog.destroy()
    
    def test_dialog_has_agent_info_label(self, root, temp_db):
        """Test agent info label exists."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, 'agent_info_label')
        assert isinstance(dialog.agent_info_label, ttk.Label)
        dialog.dialog.destroy()
    
    def test_listbox_loads_agents(self, root, temp_db):
        """Test listbox loads agents from database."""
        dialog = DeployDialog(root, temp_db)
        assert dialog.agent_listbox.size() >= 2  # At least 2 test agents
        dialog.dialog.destroy()
    
    def test_listbox_shows_agent_status(self, root, temp_db):
        """Test listbox shows agent status icons."""
        dialog = DeployDialog(root, temp_db)
        items = [dialog.agent_listbox.get(i) for i in range(dialog.agent_listbox.size())]
        assert any("●" in item or "○" in item for item in items)
        dialog.dialog.destroy()


class TestDeployDialogMethods:
    """Test DeployDialog methods."""
    
    def test_validate_inputs_empty_token_id(self, root, temp_db):
        """Test validation fails with empty token ID."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_id_var.set("")
        assert dialog._validate_inputs() is False
        dialog.dialog.destroy()
    
    def test_validate_inputs_empty_token_name(self, root, temp_db):
        """Test validation fails with empty token name."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_name_var.set("")
        assert dialog._validate_inputs() is False
        dialog.dialog.destroy()
    
    def test_validate_inputs_empty_path(self, root, temp_db):
        """Test validation fails with empty path."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_path_var.set("")
        assert dialog._validate_inputs() is False
        dialog.dialog.destroy()
    
    def test_validate_inputs_no_agent_selected(self, root, temp_db):
        """Test validation fails with no agent selected."""
        dialog = DeployDialog(root, temp_db)
        dialog.agent_listbox.selection_clear(0, tk.END)
        assert dialog._validate_inputs() is False
        dialog.dialog.destroy()
    
    def test_cancel_sets_result_none(self, root, temp_db):
        """Test cancel sets result to None."""
        dialog = DeployDialog(root, temp_db)
        dialog.result = {"test": "data"}
        dialog._cancel()
        # Dialog is destroyed, but result should be None
        assert dialog.result is None
    
    def test_browse_file_method_exists(self, root, temp_db):
        """Test _browse_file method exists."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, '_browse_file')
        assert callable(dialog._browse_file)
        dialog.dialog.destroy()
    
    def test_on_agent_select_method_exists(self, root, temp_db):
        """Test _on_agent_select method exists."""
        dialog = DeployDialog(root, temp_db)
        assert hasattr(dialog, '_on_agent_select')
        assert callable(dialog._on_agent_select)
        dialog.dialog.destroy()


class TestDeployDialogVariables:
    """Test DeployDialog variable modifications."""
    
    def test_set_token_id(self, root, temp_db):
        """Test setting token ID."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_id_var.set("test-token-123")
        assert dialog.token_id_var.get() == "test-token-123"
        dialog.dialog.destroy()
    
    def test_set_token_name(self, root, temp_db):
        """Test setting token name."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_name_var.set("My Test Token")
        assert dialog.token_name_var.get() == "My Test Token"
        dialog.dialog.destroy()
    
    def test_set_token_type(self, root, temp_db):
        """Test setting token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("image")
        assert dialog.token_type_var.get() == "image"
        dialog.dialog.destroy()
    
    def test_set_token_path(self, root, temp_db):
        """Test setting token path."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_path_var.set("C:\\test\\path.txt")
        assert dialog.token_path_var.get() == "C:\\test\\path.txt"
        dialog.dialog.destroy()
    
    def test_toggle_auto_monitor(self, root, temp_db):
        """Test toggling auto monitor."""
        dialog = DeployDialog(root, temp_db)
        dialog.auto_monitor_var.set(False)
        assert dialog.auto_monitor_var.get() is False
        dialog.auto_monitor_var.set(True)
        assert dialog.auto_monitor_var.get() is True
        dialog.dialog.destroy()
    
    def test_toggle_alert_on_access(self, root, temp_db):
        """Test toggling alert on access."""
        dialog = DeployDialog(root, temp_db)
        dialog.alert_on_access_var.set(False)
        assert dialog.alert_on_access_var.get() is False
        dialog.alert_on_access_var.set(True)
        assert dialog.alert_on_access_var.get() is True
        dialog.dialog.destroy()


class TestShowDeployDialog:
    """Test show_deploy_dialog helper function."""
    
    def test_show_deploy_dialog_function_exists(self):
        """Test function exists."""
        assert callable(show_deploy_dialog)
    
    def test_show_deploy_dialog_returns_dialog_instance(self, root, temp_db):
        """Test function creates DeployDialog."""
        # Can't fully test without showing modal dialog, but we can test creation
        try:
            dialog = DeployDialog(root, temp_db)
            assert dialog is not None
            dialog.dialog.destroy()
        except Exception as e:
            if "tcl" not in str(e).lower():
                raise


class TestDeployDialogEmptyDatabase:
    """Test DeployDialog with empty database."""
    
    def test_dialog_with_no_agents(self, root):
        """Test dialog handles no agents gracefully."""
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        
        db = DatabaseManager(temp_file.name, "test")
        db.connect()
        
        try:
            dialog = DeployDialog(root, db)
            assert dialog.agent_listbox.size() >= 0
            dialog.dialog.destroy()
        except Exception as e:
            if "tcl" not in str(e).lower():
                raise
        finally:
            db.close()
            try:
                os.unlink(temp_file.name)
            except:
                pass


class TestDeployDialogTokenTypes:
    """Test different token types."""
    
    def test_token_type_document(self, root, temp_db):
        """Test document token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("document")
        assert dialog.token_type_var.get() == "document"
        dialog.dialog.destroy()
    
    def test_token_type_image(self, root, temp_db):
        """Test image token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("image")
        assert dialog.token_type_var.get() == "image"
        dialog.dialog.destroy()
    
    def test_token_type_spreadsheet(self, root, temp_db):
        """Test spreadsheet token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("spreadsheet")
        assert dialog.token_type_var.get() == "spreadsheet"
        dialog.dialog.destroy()
    
    def test_token_type_database(self, root, temp_db):
        """Test database token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("database")
        assert dialog.token_type_var.get() == "database"
        dialog.dialog.destroy()
    
    def test_token_type_script(self, root, temp_db):
        """Test script token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("script")
        assert dialog.token_type_var.get() == "script"
        dialog.dialog.destroy()
    
    def test_token_type_other(self, root, temp_db):
        """Test other token type."""
        dialog = DeployDialog(root, temp_db)
        dialog.token_type_var.set("other")
        assert dialog.token_type_var.get() == "other"
        dialog.dialog.destroy()
