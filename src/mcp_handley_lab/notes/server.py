#!/usr/bin/env python3
"""Persistent HTTP MCP server for notes management.

This server stays alive between tool calls, enabling:
- Warm startup (load notes once)
- File watching for real-time updates
- Persistent caching and optimization
- Background processing capabilities
"""
import logging
import signal
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from .manager import NotesManager
from .tool import (
    create_note,
    delete_note,
    get_all_tags,
    get_entities_by_property,
    get_entities_linking_to,
    get_linked_entities,
    get_note,
    get_note_scope,
    get_note_types,
    get_notes_stats,
    list_entities,
    list_entities_resource,
    notes_stats_resource,
    query_entities,
    refresh_notes_database,
    search_entities,
    search_entities_semantic,
    set_manager,
    update_note,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global state for the persistent server
_manager: NotesManager | None = None
_file_observer: Observer | None = None


class NotesFileWatcher(FileSystemEventHandler):
    """File system watcher for real-time note updates."""

    def __init__(self, manager: NotesManager):
        self.manager = manager

    def on_created(self, event):
        """Handle new note files."""
        if not event.is_directory and event.src_path.endswith(".yaml"):
            logger.info(f"📝 New note detected: {event.src_path}")
            self._reload_note(event.src_path)

    def on_modified(self, event):
        """Handle modified note files."""
        if not event.is_directory and event.src_path.endswith(".yaml"):
            logger.info(f"✏️  Note modified: {event.src_path}")
            self._reload_note(event.src_path)

    def on_deleted(self, event):
        """Handle deleted note files."""
        if not event.is_directory and event.src_path.endswith(".yaml"):
            logger.info(f"🗑️  Note deleted: {event.src_path}")
            self._remove_note(event.src_path)

    def _reload_note(self, file_path: str):
        """Reload a single note file."""
        try:
            # Extract note ID from filename
            note_id = Path(file_path).stem

            # Reload the note from storage
            note = self.manager.storage.load_entity(note_id)
            if note:
                scope = self.manager.storage.get_note_scope(note_id)
                self.manager._sync_entity_to_db(note, scope or "local")
                self.manager.semantic_search.update_note(note)
                logger.debug(f"✅ Reloaded note: {note_id}")
            else:
                logger.warning(f"⚠️  Could not reload note: {note_id}")

        except Exception as e:
            logger.error(f"❌ Error reloading note {file_path}: {e}")

    def _remove_note(self, file_path: str):
        """Remove a note from memory."""
        try:
            note_id = Path(file_path).stem
            from tinydb import Query

            # Remove from database
            self.manager.db.remove(Query()._entity_id == note_id)

            # Remove from semantic search
            self.manager.semantic_search.remove_entity(note_id)

            logger.debug(f"✅ Removed note: {note_id}")

        except Exception as e:
            logger.error(f"❌ Error removing note {file_path}: {e}")


def setup_file_watching(manager: NotesManager) -> Observer:
    """Set up file system watching for real-time updates."""
    observer = Observer()
    handler = NotesFileWatcher(manager)

    # Watch both global and local directories
    global_dir = manager.storage.global_storage.entities_dir
    local_dir = manager.storage.local_storage.entities_dir

    if global_dir.exists():
        observer.schedule(handler, str(global_dir), recursive=False)
        logger.info(f"👀 Watching global notes: {global_dir}")

    if local_dir.exists():
        observer.schedule(handler, str(local_dir), recursive=False)
        logger.info(f"👀 Watching local notes: {local_dir}")

    observer.start()
    return observer


@asynccontextmanager
async def notes_lifespan(server) -> AsyncIterator[None]:
    """Manage server lifecycle - startup and shutdown."""
    global _manager, _file_observer

    logger.info("🚀 Notes server starting up...")

    try:
        # Initialize the notes manager (warm startup)
        logger.info("📚 Loading notes database...")
        _manager = NotesManager()

        # Set the manager for the MCP tools to use
        set_manager(_manager)

        # Count loaded notes
        note_count = len(_manager.db.all())
        logger.info(f"✅ Loaded {note_count} notes into memory")

        # Set up file watching for real-time updates
        logger.info("👀 Setting up file system watching...")
        _file_observer = setup_file_watching(_manager)

        logger.info("🎉 Notes server ready!")

        yield  # Server runs here

    finally:
        logger.info("🛑 Notes server shutting down...")

        # Stop file watching
        if _file_observer:
            _file_observer.stop()
            _file_observer.join()
            logger.info("👋 File watching stopped")

        # Cleanup manager
        _manager = None

        logger.info("✅ Shutdown complete")


def get_manager() -> NotesManager:
    """Get the global notes manager instance."""
    if _manager is None:
        raise RuntimeError("Notes server not initialized. Manager not available.")
    return _manager


# Create MCP server with lifespan management
mcp_server = FastMCP("Notes", lifespan=notes_lifespan)

# Register all tools with the persistent server
mcp_server.tool()(create_note)
mcp_server.tool()(get_note)
mcp_server.tool()(update_note)
mcp_server.tool()(delete_note)
mcp_server.tool()(list_entities)
mcp_server.tool()(search_entities)
mcp_server.tool()(search_entities_semantic)
mcp_server.tool()(query_entities)
mcp_server.tool()(get_entities_by_property)
mcp_server.tool()(get_linked_entities)
mcp_server.tool()(get_entities_linking_to)
mcp_server.tool()(get_note_types)
mcp_server.tool()(get_all_tags)
mcp_server.tool()(get_notes_stats)
mcp_server.tool()(refresh_notes_database)
mcp_server.tool()(get_note_scope)

# Register resources
mcp_server.resource("notes://notes")(list_entities_resource)
mcp_server.resource("notes://stats")(notes_stats_resource)


def handle_shutdown(signum, frame):
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    logger.info(f"📡 Received signal {signum}, shutting down...")
    sys.exit(0)


def main():
    """Run the persistent MCP server."""
    global _manager, _file_observer

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("🌐 Starting Notes MCP server...")
    logger.info(
        "ℹ️  Server will run on http://127.0.0.1:8000 (default StreamableHTTP port)"
    )
    logger.info("ℹ️  Use this URL in Claude Code MCP configuration")

    # Initialize manually since lifespan might not work with streamable-http
    logger.info("🚀 Notes server starting up...")

    try:
        # Initialize the notes manager (warm startup)
        logger.info("📚 Loading notes database...")
        _manager = NotesManager()

        # Set the manager for the MCP tools to use
        set_manager(_manager)

        # Count loaded notes
        note_count = len(_manager.db.all())
        logger.info(f"✅ Loaded {note_count} notes into memory")

        # Set up file watching for real-time updates
        logger.info("👀 Setting up file system watching...")
        _file_observer = setup_file_watching(_manager)

        logger.info("🎉 Notes server ready!")

        # Run the server using streamable HTTP transport
        mcp_server.run(transport="streamable-http")

    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise
    finally:
        # Cleanup
        if _file_observer:
            _file_observer.stop()
            _file_observer.join()
            logger.info("👋 File watching stopped")


if __name__ == "__main__":
    main()
