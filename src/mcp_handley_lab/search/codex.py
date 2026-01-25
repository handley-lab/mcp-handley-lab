"""Codex CLI transcript search."""

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

DB_NAME = "codex"

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


def _get_codex_dir() -> Path:
    """Get ~/.codex directory."""
    return Path.home() / ".codex"


def _extract_text(entry: dict) -> str:
    """Extract searchable text from Codex entry."""
    texts = []
    payload = entry.get("payload", {})
    ptype = payload.get("type")
    etype = entry.get("type")

    if etype == "event_msg":
        msg_type = payload.get("type")
        if msg_type == "agent_reasoning":
            texts.append(payload.get("text", ""))
        elif msg_type == "user_message":
            texts.append(payload.get("message", ""))

    elif etype == "response_item":
        if ptype == "message":
            for block in payload.get("content", []):
                if isinstance(block, dict) and block.get("type") == "input_text":
                    texts.append(block.get("text", ""))
        elif ptype == "reasoning":
            for summary in payload.get("summary", []):
                if isinstance(summary, dict) and summary.get("type") == "summary_text":
                    texts.append(summary.get("text", ""))
        elif ptype == "function_call":
            texts.append(f"tool:{payload.get('name', '')}")
            args = payload.get("arguments", "")
            if isinstance(args, str):
                texts.append(args)
        elif ptype == "function_call_output":
            texts.append(payload.get("output", ""))

    elif etype == "session_meta":
        cwd = payload.get("cwd", "")
        if cwd:
            texts.append(f"cwd:{cwd}")

    return "\n".join(filter(None, texts))


def _classify_type(entry: dict) -> str:
    """Classify entry into user/assistant/system/tool type."""
    etype = entry.get("type")
    payload = entry.get("payload", {})
    ptype = payload.get("type")

    if etype == "session_meta":
        return "system"
    elif etype == "event_msg":
        msg_type = payload.get("type")
        if msg_type == "user_message":
            return "user"
        elif msg_type == "agent_reasoning":
            return "assistant"
        return "system"
    elif etype == "response_item":
        role = payload.get("role")
        if role == "user":
            return "user"
        if ptype in ("message", "reasoning"):
            return "assistant"
        if ptype in ("function_call", "function_call_output"):
            return "tool"
        return "assistant"
    return "system"


def _find_files() -> list[Path]:
    """Find all Codex transcript JSONL files."""
    codex_dir = _get_codex_dir()
    sessions_dir = codex_dir / "sessions"
    if not sessions_dir.exists():
        return []
    return list(sessions_dir.glob("**/*.jsonl"))


def _parse_file(file_path: Path) -> list[tuple]:
    """Parse JSONL file, streaming line by line. Returns entry tuples for batch insert."""
    entries = []
    session_id = file_path.stem
    # Extract project path from session_meta if available
    project_path = None
    idx = 0  # Track position of kept entries only

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                # Get project path from session_meta
                if entry.get("type") == "session_meta":
                    project_path = entry.get("payload", {}).get("cwd")

                entry_type = _classify_type(entry)
                content_text = _extract_text(entry)

                # Skip entries with no meaningful content
                if not content_text.strip():
                    continue

                entries.append(
                    (
                        str(file_path),
                        session_id,
                        project_path,
                        None,  # uuid
                        entry_type,
                        entry.get("timestamp"),
                        content_text,
                        entry.get("payload", {}).get("model"),
                        None,  # cost_usd not available in codex format
                        line.strip(),
                        idx,  # Position in session
                    )
                )
                idx += 1
            except json.JSONDecodeError:
                continue
    return entries


def sync(full: bool = False) -> dict:
    """Sync Codex transcripts to database. Uses file lock to prevent concurrent syncs."""
    with file_lock("codex"):
        conn = get_connection("codex")
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
) -> list[dict]:
    """Full-text search across Codex transcripts."""
    conn = get_connection("codex")
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
        },
    )


def stats() -> dict:
    """Get Codex usage statistics."""
    conn = get_connection("codex")
    _init_schema(conn)

    totals = conn.execute(
        """
        SELECT COUNT(*) as entries,
               COUNT(DISTINCT session_id) as sessions,
               COUNT(DISTINCT project_path) as projects
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
        "by_type": {row["type"]: row["count"] for row in by_type},
    }
