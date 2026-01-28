"""Shared sync orchestration for transcript search.

Uses the adapter protocol: each source implements discover_items() and load_entries().
This module handles the common sync logic: change detection, DB updates, cleanup.
"""

import logging
import sqlite3

from mcp_handley_lab.search import db

logger = logging.getLogger(__name__)


def sync_source(
    conn: sqlite3.Connection,
    source: str,
    discover_items: callable,
    load_entries: callable,
    full: bool = False,
) -> dict:
    """Sync a single source using its adapter functions.

    Args:
        conn: Unified DB connection.
        source: Source name (claude, codex, gemini, mcp).
        discover_items: () -> list[SyncItem]
        load_entries: (SyncItem) -> list[RawEntry]
        full: If True, ignore fingerprints and resync everything.

    Returns:
        Dict with files, entries, skipped, deleted counts.
    """
    stats = {"files": 0, "entries": 0, "skipped": 0, "deleted": 0}

    items = discover_items()
    active_keys = {item.session_key for item in items}

    for item in items:
        if not full:
            stored_fp = db.get_sync_fingerprint(conn, source, item.session_key)
            if stored_fp == item.fingerprint:
                stats["skipped"] += 1
                continue

        # Load entries first (adapters may update item.project during load)
        raw_entries = load_entries(item)

        # Get or create session (after load so item.project is populated)
        session_id = db.get_or_create_session(
            conn, source, item.session_key, item.display_name, item.project
        )

        # Delete existing entries for re-sync
        db.delete_session_entries(conn, session_id)
        if raw_entries:
            entry_tuples = [
                (
                    e.idx,
                    e.role,
                    db.parse_timestamp(e.timestamp),
                    e.timestamp,
                    e.content,
                    e.model,
                    e.cost_usd,
                    e.raw_json,
                )
                for e in raw_entries
            ]
            db.insert_entries(conn, session_id, entry_tuples)

        # Update session stats
        db.update_session_stats(conn, session_id)

        # Update sync state
        db.update_sync_state(
            conn,
            source,
            item.session_key,
            len(raw_entries),
            mtime=item.mtime,
            size=item.size,
            tip_sha=item.tip_sha,
        )

        stats["files"] += 1
        stats["entries"] += len(raw_entries)

    # Cleanup stale sessions
    stats["deleted"] = db.cleanup_stale_sessions(conn, source, active_keys)

    return stats


def sync_all_sources(source_registry: dict, full: bool = False) -> dict[str, dict]:
    """Sync all registered sources.

    Args:
        source_registry: Dict mapping source name to module with discover_items/load_entries.
        full: If True, resync everything.

    Returns:
        Dict mapping source name to sync stats.
    """
    with db.sync_lock():
        conn = db.ensure_db()
        try:
            conn.execute("BEGIN IMMEDIATE")

            if full:
                conn.execute("DELETE FROM entries")
                conn.execute("DELETE FROM sessions")
                conn.execute("DELETE FROM sync_state")

            results = {}
            for source_name, module in source_registry.items():
                results[source_name] = sync_source(
                    conn,
                    source_name,
                    module.discover_items,
                    module.load_entries,
                    full=full,
                )

            conn.commit()
            return results
        except Exception:
            conn.rollback()
            raise


def sync_single_source(source_name: str, module, full: bool = False) -> dict:
    """Sync a single source.

    Args:
        source_name: Source identifier (claude, codex, gemini, mcp).
        module: Source module with discover_items/load_entries.
        full: If True, resync everything for this source.
    """
    with db.sync_lock():
        conn = db.ensure_db()
        try:
            conn.execute("BEGIN IMMEDIATE")

            if full:
                # Only delete this source's data
                conn.execute(
                    """DELETE FROM entries WHERE session_id IN
                       (SELECT id FROM sessions WHERE source = ?)""",
                    (source_name,),
                )
                conn.execute("DELETE FROM sessions WHERE source = ?", (source_name,))
                conn.execute("DELETE FROM sync_state WHERE source = ?", (source_name,))

            result = sync_source(
                conn, source_name, module.discover_items, module.load_entries, full=full
            )
            conn.commit()
            return result
        except Exception:
            conn.rollback()
            raise
