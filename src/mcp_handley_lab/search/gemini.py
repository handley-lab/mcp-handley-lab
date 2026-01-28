"""Gemini CLI transcript search."""

import json
from pathlib import Path

from mcp_handley_lab.search.common import (
    check_sync_needed,
    cleanup_deleted_files,
    ensure_idx_column,
    file_lock,
    fts_search,
    get_connection,
    setup_fts_with_triggers,
    update_sync_meta,
)

DB_NAME = "gemini"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL,
    session_id TEXT NOT NULL,
    project_path TEXT,
    uuid TEXT,
    type TEXT NOT NULL,
    timestamp TEXT,
    content_text TEXT,
    model TEXT,
    cost_usd REAL,
    raw_json TEXT,
    idx INTEGER
);

CREATE TABLE IF NOT EXISTS sync_meta (
    file_path TEXT PRIMARY KEY,
    mtime REAL,
    size INTEGER,
    entry_count INTEGER
);

CREATE INDEX IF NOT EXISTS idx_file_path ON entries(file_path);
CREATE INDEX IF NOT EXISTS idx_session ON entries(session_id);
CREATE INDEX IF NOT EXISTS idx_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_timestamp ON entries(timestamp);
"""


def _init_schema(conn):
    """Initialize database schema and FTS triggers."""
    conn.executescript(SCHEMA)
    setup_fts_with_triggers(conn)
    ensure_idx_column(conn)  # Auto-migrate existing DBs, forces resync if needed


def _get_gemini_dir() -> Path:
    """Get ~/.gemini/tmp directory."""
    return Path.home() / ".gemini" / "tmp"


def _extract_text(msg: dict) -> str:
    """Extract searchable text from Gemini message."""
    texts = [msg.get("content", "")]

    # Extract thoughts
    for thought in msg.get("thoughts", []):
        if isinstance(thought, dict):
            texts.append(thought.get("subject", ""))
            texts.append(thought.get("description", ""))

    # Extract tool calls
    for tool in msg.get("toolCalls", []):
        if isinstance(tool, dict):
            texts.append(f"tool:{tool.get('name', '')}")
            args = tool.get("args", {})
            if isinstance(args, dict):
                for v in args.values():
                    if isinstance(v, str):
                        texts.append(v)
            texts.append(tool.get("resultDisplay", ""))

    return "\n".join(filter(None, texts))


def _classify_type(msg: dict) -> str:
    """Classify message into user/assistant type."""
    msg_type = msg.get("type", "")
    if msg_type == "user":
        return "user"
    elif msg_type == "gemini":
        return "assistant"
    return "system"


def _find_files() -> list[Path]:
    """Find all Gemini chat JSON files."""
    gemini_dir = _get_gemini_dir()
    if not gemini_dir.exists():
        return []
    return list(gemini_dir.glob("*/chats/*.json"))


def _parse_file(file_path: Path) -> list[tuple]:
    """Parse JSON file. Returns entry tuples for batch insert."""
    entries = []

    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    session_id = data.get("sessionId", file_path.stem)
    project_hash = data.get("projectHash", file_path.parent.parent.name)
    idx = 0  # Track position of kept entries only

    for msg in data.get("messages", []):
        msg_type = _classify_type(msg)
        content_text = _extract_text(msg)

        # Skip messages with no meaningful content
        if not content_text.strip():
            continue

        # Get model info
        model = msg.get("model")

        # Calculate approximate cost from tokens if available
        tokens = msg.get("tokens", {})
        cost_usd = None
        if tokens:
            # Rough estimate based on Gemini pricing
            input_tokens = tokens.get("input", 0) + tokens.get("cached", 0)
            output_tokens = tokens.get("output", 0) + tokens.get("thoughts", 0)
            # Very rough approximation: $0.075/1M input, $0.30/1M output for 2.5 Pro
            cost_usd = (input_tokens * 0.075 + output_tokens * 0.30) / 1_000_000

        entries.append(
            (
                str(file_path),
                session_id,
                project_hash,
                msg.get("id"),
                msg_type,
                msg.get("timestamp"),
                content_text,
                model,
                cost_usd,
                json.dumps(msg),
                idx,  # Position in session
            )
        )
        idx += 1

    return entries


def sync(full: bool = False) -> dict:
    """Sync Gemini transcripts to database. Uses file lock to prevent concurrent syncs."""
    with file_lock("gemini"):
        conn = get_connection("gemini")
        _init_schema(conn)
        conn.commit()  # Commit any schema changes before starting sync transaction

        try:
            conn.execute("BEGIN IMMEDIATE")

            if full:
                conn.execute("DELETE FROM entries")
                conn.execute("DELETE FROM sync_meta")

            files = _find_files()
            existing_files = {str(f) for f in files}

            stats = {"files": 0, "entries": 0, "skipped": 0, "deleted": 0}

            for file_path in files:
                if not full and not check_sync_needed(conn, file_path):
                    stats["skipped"] += 1
                    continue

                conn.execute(
                    "DELETE FROM entries WHERE file_path = ?", (str(file_path),)
                )

                entries = _parse_file(file_path)
                if entries:
                    conn.executemany(
                        """
                        INSERT INTO entries (file_path, session_id, project_path, uuid, type,
                                           timestamp, content_text, model, cost_usd, raw_json, idx)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        entries,
                    )

                update_sync_meta(conn, file_path, len(entries))
                stats["files"] += 1
                stats["entries"] += len(entries)

            stats["deleted"] = cleanup_deleted_files(conn, existing_files)

            conn.commit()
        except Exception:
            conn.rollback()
            raise

        return stats


def search(
    query: str = "",
    project: str = "",
    type: str = "",
    limit: int = 20,
    since: str = "",
    file_path: str = "",
) -> list[dict]:
    """Full-text search across Gemini transcripts."""
    conn = get_connection("gemini")
    _init_schema(conn)

    if not query:
        sql = "SELECT * FROM entries WHERE 1=1"
        params: list = []

        if project:
            sql += " AND project_path LIKE ?"
            params.append(f"%{project}%")
        if type:
            sql += " AND type = ?"
            params.append(type)
        if since:
            sql += " AND timestamp >= ?"
            params.append(since)
        if file_path:
            sql += " AND file_path = ?"
            params.append(file_path)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return [dict(row) for row in conn.execute(sql, params)]

    return fts_search(
        conn,
        query,
        limit=limit,
        filters={
            "project_path": project or None,
            "type": type or None,
            "timestamp": since or None,
            "file_path": file_path or None,
        },
    )


def stats() -> dict:
    """Get Gemini usage statistics."""
    conn = get_connection("gemini")
    _init_schema(conn)

    totals = conn.execute(
        """
        SELECT COUNT(*) as entries,
               COUNT(DISTINCT session_id) as sessions,
               COUNT(DISTINCT project_path) as projects,
               SUM(cost_usd) as total_cost
        FROM entries
        """
    ).fetchone()

    by_type = conn.execute(
        """
        SELECT type, COUNT(*) as count
        FROM entries
        GROUP BY type
        ORDER BY count DESC
        """
    ).fetchall()

    return {
        "entries": totals["entries"],
        "sessions": totals["sessions"],
        "projects": totals["projects"],
        "total_cost": totals["total_cost"] or 0.0,
        "by_type": {row["type"]: row["count"] for row in by_type},
    }
