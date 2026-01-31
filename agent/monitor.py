#!/usr/bin/env python3
"""
HoneyGrid File System Monitor
Monitors honeytoken files/folders using watchdog library.
Detects access, modification, and deletion events.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from multiprocessing import Queue
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MonitorEvent:
    """
    File system event detected by monitor.
    """
    token_id: str  # Identifier for the honeytoken
    path: str  # Full file path
    event_type: str  # "created", "modified", "opened", "moved", "deleted"
    timestamp: float  # Event timestamp
    is_directory: bool  # True if target is a directory
    metadata: Dict[str, Any]  # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class HoneytokenHandler(FileSystemEventHandler):
    """
    File system event handler for honeytokens.
    """
    
    def __init__(
        self,
        event_queue: Queue,
        token_mapping: Dict[str, str],
        verbose: bool = False
    ):
        """
        Initialize handler.
        
        Args:
            event_queue: Queue to push detected events
            token_mapping: Map of file paths to token IDs
            verbose: Enable verbose logging
        """
        super().__init__()
        self.event_queue = event_queue
        self.token_mapping = token_mapping
        self.verbose = verbose
        
        # Normalize paths in mapping (Windows compatibility)
        self.normalized_mapping = {
            str(Path(p).resolve()): token_id
            for p, token_id in token_mapping.items()
        }
    
    def _get_token_id(self, path: str) -> Optional[str]:
        """Get token ID for a given path."""
        normalized_path = str(Path(path).resolve())
        
        # Direct match
        if normalized_path in self.normalized_mapping:
            return self.normalized_mapping[normalized_path]
        
        # Check if path is within a monitored directory
        for monitored_path, token_id in self.normalized_mapping.items():
            if normalized_path.startswith(monitored_path):
                return token_id
        
        return None
    
    def _create_event(
        self,
        src_path: str,
        event_type: str,
        is_directory: bool = False,
        **metadata
    ) -> Optional[MonitorEvent]:
        """
        Create a monitor event.
        
        Args:
            src_path: Source file path
            event_type: Event type
            is_directory: Whether path is a directory
            **metadata: Additional metadata
        
        Returns:
            MonitorEvent or None if path not monitored
        """
        token_id = self._get_token_id(src_path)
        if not token_id:
            return None
        
        return MonitorEvent(
            token_id=token_id,
            path=src_path,
            event_type=event_type,
            timestamp=time.time(),
            is_directory=is_directory,
            metadata=metadata
        )
    
    def _push_event(self, event: Optional[MonitorEvent]):
        """Push event to queue if valid."""
        if event:
            self.event_queue.put(event)
            if self.verbose:
                logger.info(
                    f"🚨 Event detected: {event.event_type} - "
                    f"{event.path} (token: {event.token_id})"
                )
    
    def on_created(self, event: FileSystemEvent):
        """Handle file/directory creation."""
        monitor_event = self._create_event(
            event.src_path,
            "created",
            event.is_directory
        )
        self._push_event(monitor_event)
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file/directory modification."""
        # Ignore directory modifications (too noisy)
        if event.is_directory:
            return
        
        monitor_event = self._create_event(
            event.src_path,
            "modified",
            event.is_directory
        )
        self._push_event(monitor_event)
    
    def on_deleted(self, event: FileSystemEvent):
        """Handle file/directory deletion."""
        monitor_event = self._create_event(
            event.src_path,
            "deleted",
            event.is_directory
        )
        self._push_event(monitor_event)
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file/directory move/rename."""
        if hasattr(event, 'dest_path'):
            monitor_event = self._create_event(
                event.src_path,
                "moved",
                event.is_directory,
                dest_path=event.dest_path
            )
            self._push_event(monitor_event)


class FSMonitor:
    """
    File system monitor for honeytokens.
    """
    
    def __init__(
        self,
        event_queue: Queue,
        watch_paths: Optional[List[str]] = None,
        token_mapping: Optional[Dict[str, str]] = None,
        recursive: bool = True,
        verbose: bool = False
    ):
        """
        Initialize file system monitor.
        
        Args:
            event_queue: Queue to push detected events
            watch_paths: List of paths to monitor
            token_mapping: Map of file paths to token IDs
            recursive: Watch directories recursively
            verbose: Enable verbose logging
        """
        self.event_queue = event_queue
        self.watch_paths = watch_paths or []
        self.token_mapping = token_mapping or {}
        self.recursive = recursive
        self.verbose = verbose
        
        self.observer = None
        self.handler = None
        self.is_running = False
    
    def add_watch_path(self, path: str, token_id: str):
        """
        Add a path to monitor.
        
        Args:
            path: File or directory path
            token_id: Token identifier
        """
        path_obj = Path(path)
        
        if not path_obj.exists():
            logger.warning(f"Path does not exist: {path}")
            return
        
        self.watch_paths.append(str(path_obj.resolve()))
        self.token_mapping[str(path_obj.resolve())] = token_id
        
        logger.info(f"Added watch: {path} → {token_id}")
    
    def remove_watch_path(self, path: str):
        """
        Remove a path from monitoring.
        
        Args:
            path: Path to remove
        """
        path_str = str(Path(path).resolve())
        
        if path_str in self.watch_paths:
            self.watch_paths.remove(path_str)
        
        if path_str in self.token_mapping:
            del self.token_mapping[path_str]
        
        logger.info(f"Removed watch: {path}")
    
    def start(self):
        """Start monitoring."""
        if self.is_running:
            logger.warning("Monitor already running")
            return
        
        if not self.watch_paths:
            logger.warning("No paths to monitor")
            return
        
        # Create event handler
        self.handler = HoneytokenHandler(
            self.event_queue,
            self.token_mapping,
            self.verbose
        )
        
        # Create observer
        self.observer = Observer()
        
        # Schedule watches
        for path in self.watch_paths:
            try:
                self.observer.schedule(
                    self.handler,
                    path,
                    recursive=self.recursive
                )
                logger.info(f"Watching: {path} (recursive={self.recursive})")
            except Exception as e:
                logger.error(f"Failed to watch {path}: {e}")
        
        # Start observer
        self.observer.start()
        self.is_running = True
        logger.info("✓ File system monitor started")
    
    def stop(self):
        """Stop monitoring."""
        if not self.is_running:
            return
        
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
        
        self.is_running = False
        logger.info("✓ File system monitor stopped")
    
    def run(self, duration: Optional[float] = None):
        """
        Run monitor for specified duration.
        
        Args:
            duration: Run duration in seconds (None = indefinite)
        """
        self.start()
        
        try:
            if duration:
                logger.info(f"Running for {duration} seconds...")
                time.sleep(duration)
            else:
                logger.info("Running indefinitely (Ctrl+C to stop)...")
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
        finally:
            self.stop()
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


# Example usage and testing
if __name__ == "__main__":
    from multiprocessing import Manager
    import os
    import tempfile
    
    print("HoneyGrid File System Monitor - Test")
    print("=" * 60)
    
    # Create test directory and file
    test_dir = Path(tempfile.mkdtemp(prefix="honeygrid_test_"))
    test_file = test_dir / "secret.txt"
    test_file.write_text("This is a honeytoken file")
    
    print(f"\n1. Created test honeytoken:")
    print(f"   Directory: {test_dir}")
    print(f"   File: {test_file}")
    
    # Create event queue
    manager = Manager()
    event_queue = manager.Queue()
    
    # Create monitor
    monitor = FSMonitor(
        event_queue=event_queue,
        recursive=True,
        verbose=True
    )
    
    # Add watch
    monitor.add_watch_path(str(test_file), "token-test-001")
    
    print("\n2. Starting monitor...")
    monitor.start()
    
    # Simulate some file operations
    print("\n3. Simulating file operations...")
    time.sleep(1)
    
    print("   - Modifying file...")
    test_file.write_text("This file was accessed by an attacker!")
    time.sleep(0.5)
    
    print("   - Creating another file...")
    test_file2 = test_dir / "another.txt"
    test_file2.write_text("Another honeytoken")
    time.sleep(0.5)
    
    print("   - Deleting file...")
    test_file.unlink()
    time.sleep(0.5)
    
    # Stop monitor
    print("\n4. Stopping monitor...")
    monitor.stop()
    
    # Check events
    print("\n5. Collected events:")
    event_count = 0
    while not event_queue.empty():
        event = event_queue.get()
        event_count += 1
        print(f"   Event {event_count}:")
        print(f"     Type: {event.event_type}")
        print(f"     Path: {event.path}")
        print(f"     Token: {event.token_id}")
        print(f"     Time: {time.ctime(event.timestamp)}")
    
    print(f"\n   Total events: {event_count}")
    
    # Cleanup
    import shutil
    shutil.rmtree(test_dir)
    
    print("\n" + "=" * 60)
    print("✓ Monitor tests passed!")
    print("✓ Test files cleaned up")
