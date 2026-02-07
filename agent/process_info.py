#!/usr/bin/env python3
"""
HoneyGrid Process Information Capture
Captures process details when files are accessed.
"""

import psutil
import os
import platform
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ProcessCapture:
    """
    Capture information about processes accessing files.
    
    This class provides utilities to identify and capture details about
    processes that access monitored honeytoken files, including:
    - Process name and ID (PID)
    - User running the process
    - Command line arguments
    - Parent process information
    """

    @staticmethod
    def get_process_by_file_access(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Attempt to determine which process accessed a file.
        
        Note: This is best-effort and may not work on all systems.
        Windows: Uses file handle enumeration (requires admin)
        Linux: Uses /proc filesystem
        
        Args:
            file_path: Path to the file that was accessed
            
        Returns:
            Dictionary with process info or None if process cannot be determined
        """
        try:
            # Normalize path for comparison
            normalized_path = os.path.abspath(file_path)
            
            # Try platform-specific methods
            if platform.system() == "Windows":
                return ProcessCapture._get_process_windows(normalized_path)
            elif platform.system() == "Linux":
                return ProcessCapture._get_process_linux(normalized_path)
            else:
                logger.warning(f"Process capture not supported on {platform.system()}")
                return None
                
        except Exception as e:
            logger.debug(f"Failed to capture process info: {e}")
            return None

    @staticmethod
    def _get_process_windows(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Windows-specific process capture using file handle enumeration.
        
        Args:
            file_path: Normalized file path
            
        Returns:
            Process info dict or None
        """
        try:
            # On Windows, we can try to find handles to the file
            # This requires administrative privileges
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
                try:
                    # Try to get open files for this process
                    open_files = proc.open_files()
                    for file_info in open_files:
                        if file_info.path.lower() == file_path.lower():
                            return ProcessCapture._format_process_info(proc)
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    # Skip processes we can't access
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Windows process capture failed: {e}")
            return None

    @staticmethod
    def _get_process_linux(file_path: str) -> Optional[Dict[str, Any]]:
        """
        Linux-specific process capture using /proc filesystem.
        
        Args:
            file_path: Normalized file path
            
        Returns:
            Process info dict or None
        """
        try:
            # On Linux, scan /proc/*/fd to find file descriptors
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
                try:
                    fd_dir = f"/proc/{proc.pid}/fd"
                    if os.path.exists(fd_dir):
                        for fd in os.listdir(fd_dir):
                            try:
                                fd_path = os.path.join(fd_dir, fd)
                                link_target = os.readlink(fd_path)
                                if link_target == file_path:
                                    return ProcessCapture._format_process_info(proc)
                            except (OSError, FileNotFoundError):
                                continue
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Linux process capture failed: {e}")
            return None

    @staticmethod
    def _format_process_info(proc: psutil.Process) -> Dict[str, Any]:
        """
        Format process information into standardized dictionary.
        
        Args:
            proc: psutil.Process object
            
        Returns:
            Formatted process info dictionary
        """
        try:
            # Get basic process info
            with proc.oneshot():
                name = proc.name()
                pid = proc.pid
                cmdline = " ".join(proc.cmdline()) if proc.cmdline() else ""
                username = proc.username()
                
                # Get parent process if available
                try:
                    ppid = proc.ppid()
                    pname = proc.parent().name() if proc.parent() else None
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    ppid = None
                    pname = None
                
                return {
                    "process_name": name,
                    "process_id": pid,
                    "process_user": username,
                    "process_cmdline": cmdline[:500],  # Limit to 500 chars
                    "parent_id": ppid,
                    "parent_name": pname,
                }
        
        except Exception as e:
            logger.debug(f"Failed to format process info: {e}")
            return {
                "process_name": "unknown",
                "process_id": None,
                "process_user": "unknown",
                "process_cmdline": "",
            }

    @staticmethod
    def get_current_process_info() -> Dict[str, Any]:
        """
        Get information about the current process (agent itself).
        
        Returns:
            Dictionary with current process information
        """
        try:
            current_pid = os.getpid()
            proc = psutil.Process(current_pid)
            return ProcessCapture._format_process_info(proc)
        except Exception as e:
            logger.warning(f"Failed to get current process info: {e}")
            return {
                "process_name": "honeygrid-agent",
                "process_id": current_pid,
                "process_user": "unknown",
                "process_cmdline": "",
            }

    @staticmethod
    def get_system_processes_accessing_path(file_path: str) -> list:
        """
        Get all processes that might have access to a file path.
        
        This is useful for forensic analysis after a honeytoken trigger.
        
        Args:
            file_path: Path to check
            
        Returns:
            List of process info dictionaries
        """
        processes = []
        normalized_path = os.path.abspath(file_path)
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'username']):
                try:
                    open_files = proc.open_files()
                    for file_info in open_files:
                        if normalized_path.lower() in file_info.path.lower():
                            processes.append(ProcessCapture._format_process_info(proc))
                            break
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    continue
        except Exception as e:
            logger.debug(f"Error scanning processes: {e}")
        
        return processes


# Example usage and testing
if __name__ == "__main__":
    print("HoneyGrid Process Capture - Test")
    print("=" * 60)

    # Test getting current process info
    print("\n1. Current Process Info:")
    info = ProcessCapture.get_current_process_info()
    for key, value in info.items():
        print(f"   {key}: {value}")

    # Test system processes (will list processes)
    print("\n2. Scanning for processes accessing this script...")
    script_path = os.path.abspath(__file__)
    processes = ProcessCapture.get_system_processes_accessing_path(script_path)
    if processes:
        for i, proc in enumerate(processes[:5], 1):
            print(f"   Process {i}: {proc['process_name']} (PID: {proc['process_id']})")
    else:
        print("   No processes found (this is normal, might require admin)")

    print("\n" + "=" * 60)
    print("✓ Process capture module loaded")
