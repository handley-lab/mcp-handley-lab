#!/usr/bin/env python3
"""
Persistent Notes HTTP Server

Runs the notes MCP tool as a persistent HTTP server to eliminate startup costs.
Maintains notes loaded in memory between requests for ~10ms response times.
"""

import argparse
import os
import sys
import threading
import time
from pathlib import Path

from mcp_handley_lab.notes.manager import NotesManager
from mcp_handley_lab.notes.tool import mcp, set_manager

# Add src to path so we can import the notes module
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Global state for the persistent server
_start_time = time.time()
_manager_lock = threading.Lock()
_persistent_manager: NotesManager | None = None


def create_persistent_manager() -> NotesManager:
    """Create and initialize a persistent notes manager."""
    global _persistent_manager

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

            # Set this as the global manager for all tool calls
            set_manager(_persistent_manager)

        return _persistent_manager


def main():
    """Start the persistent notes HTTP server."""
    parser = argparse.ArgumentParser(description="Persistent Notes HTTP Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", default=8001, type=int, help="Port to bind to")
    parser.add_argument("--notes-dir", help="Override notes directory location")

    args = parser.parse_args()

    print("Starting Persistent Notes HTTP Server...")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")

    if args.notes_dir:
        print(f"Notes directory: {args.notes_dir}")
        os.environ["NOTES_DIR"] = args.notes_dir

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
    except Exception as e:
        print(f"[{time.time() - _start_time:.2f}s] Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
