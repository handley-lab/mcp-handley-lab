#!/usr/bin/env python3
"""
Persistent Notes HTTP Server

Runs the notes MCP tool as a persistent HTTP server to eliminate startup costs.
Maintains notes loaded in memory between requests for ~10ms response times.
"""

import argparse
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .manager import NotesManager
from .tool import mcp

# Global state for the persistent server
_start_time = time.time()
_manager_lock = threading.Lock()
_persistent_manager: NotesManager | None = None
_file_observer: Observer | None = None


class NotesFileHandler(FileSystemEventHandler):
    """Handles filesystem events for YAML note files."""

    def __init__(self, manager: NotesManager):
        self.manager = manager
        super().__init__()

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith((".yaml", ".yml")):
            self._refresh_file(event.src_path)

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith((".yaml", ".yml")):
            self._refresh_file(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and event.src_path.endswith((".yaml", ".yml")):
            self._refresh_file(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            if event.src_path.endswith((".yaml", ".yml")):
                self._refresh_file(event.src_path)  # Remove old location
            if event.dest_path.endswith((".yaml", ".yml")):
                self._refresh_file(event.dest_path)  # Add new location

    def _refresh_file(self, file_path: str):
        """Refresh a single file in the manager's database."""
        with _manager_lock:
            if self.manager:
                print(
                    f"[{time.time() - _start_time:.2f}s] File change detected: {file_path}"
                )
                start = time.time()
                success = self.manager.refresh_single_file(file_path)
                elapsed = time.time() - start
                if success:
                    print(
                        f"[{time.time() - _start_time:.2f}s] Refreshed single file in {elapsed:.3f}s"
                    )
                else:
                    print(
                        f"[{time.time() - _start_time:.2f}s] File refresh failed in {elapsed:.3f}s"
                    )


def create_persistent_manager() -> NotesManager:
    """Create and initialize a persistent notes manager."""
    global _persistent_manager, _file_observer

    with _manager_lock:
        if _persistent_manager is None:
            print(
                f"[{time.time() - _start_time:.2f}s] Initializing persistent notes manager..."
            )
            start = time.time()

            # Create manager and load all notes into memory
            _persistent_manager = NotesManager()

            # Force initialization of the database
            stats = _persistent_manager.get_stats()

            elapsed = time.time() - start
            print(
                f"[{time.time() - _start_time:.2f}s] Loaded {stats['total_notes']} notes in {elapsed:.3f}s"
            )

            # Start file watching
            _start_file_watching(_persistent_manager)

        return _persistent_manager


def _start_file_watching(manager: NotesManager):
    """Start watching notes directories for file changes."""
    global _file_observer

    if _file_observer is None:
        _file_observer = Observer()
        event_handler = NotesFileHandler(manager)

        # Watch both global and local notes directories
        global_dir = Path.home() / ".mcp_handley_lab" / "notes"
        local_dir = Path(".mcp_handley_lab") / "notes"

        if global_dir.exists():
            _file_observer.schedule(event_handler, str(global_dir), recursive=True)
            print(
                f"[{time.time() - _start_time:.2f}s] Watching global notes: {global_dir}"
            )

        if local_dir.exists():
            _file_observer.schedule(event_handler, str(local_dir), recursive=True)
            print(
                f"[{time.time() - _start_time:.2f}s] Watching local notes: {local_dir}"
            )

        _file_observer.start()
        print(f"[{time.time() - _start_time:.2f}s] File watching active")


def _stop_file_watching():
    """Stop the file watching observer."""
    global _file_observer

    if _file_observer:
        _file_observer.stop()
        _file_observer.join()
        _file_observer = None
        print(f"[{time.time() - _start_time:.2f}s] File watching stopped")


def main():
    """Start the persistent notes HTTP server."""
    parser = argparse.ArgumentParser(description="Persistent Notes HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind to")

    args = parser.parse_args()

    print("Starting Persistent Notes HTTP Server...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")

    # Initialize the persistent manager (this triggers the slow initial load)
    try:
        create_persistent_manager()
        print(
            f"[{time.time() - _start_time:.2f}s] Server ready - all subsequent requests will be fast!"
        )

        # Start the HTTP server
        print(
            f"[{time.time() - _start_time:.2f}s] Starting HTTP server on {args.host}:{args.port}"
        )
        mcp.run(transport="streamable-http")

    except KeyboardInterrupt:
        print(f"\n[{time.time() - _start_time:.2f}s] Server shutting down...")
        _stop_file_watching()
    except Exception as e:
        print(f"[{time.time() - _start_time:.2f}s] Error: {e}")
        _stop_file_watching()
        import sys
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
