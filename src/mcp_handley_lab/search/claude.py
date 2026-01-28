"""Claude Code transcript search."""

import json
from pathlib import Path

from mcp_handley_lab.claude.transcript import _get_claude_dir
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

DB_NAME = "claude"

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

CREATE TABLE IF NOT EXISTS tool_uses (
    id TEXT,
    entry_id INTEGER REFERENCES entries(id) ON DELETE CASCADE,
    tool_name TEXT,
    duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS usage (
    entry_id INTEGER PRIMARY KEY REFERENCES entries(id) ON DELETE CASCADE,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read INTEGER,
    cache_create INTEGER
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


def _extract_text(entry: dict) -> str:
    """Extract ALL searchable text from Claude entry."""
    texts = []
    etype = entry.get("type")

    if etype in ("user", "assistant"):
        msg = entry.get("message", {})
        content = msg.get("content", "")

        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type")
                    if btype == "text":
                        texts.append(block.get("text", ""))
                    elif btype == "thinking":
                        texts.append(block.get("thinking", ""))
                    elif btype == "tool_use":
                        texts.append(f"tool:{block.get('name', '')}")
                        inp = block.get("input", {})
                        if isinstance(inp, dict):
                            for v in inp.values():
                                if isinstance(v, str):
                                    texts.append(v)

        # Tool results
        tool_result = entry.get("toolUseResult")
        if tool_result:
            if isinstance(tool_result, str):
                texts.append(tool_result)
            elif isinstance(tool_result, list):
                for item in tool_result:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(item.get("text", ""))

    elif etype == "system":
        texts.append(entry.get("content", ""))
    elif etype == "summary":
        texts.append(entry.get("summary", ""))

    return "\n".join(filter(None, texts))


def _find_files() -> list[Path]:
    """Find all Claude transcript JSONL files, excluding agent files."""
    claude_dir = _get_claude_dir()
    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return []
    files = []
    for f in projects_dir.glob("*/*.jsonl"):
        if not f.name.startswith("agent-"):
            files.append(f)
    return files


def _parse_file(file_path: Path) -> list[tuple]:
    """Parse JSONL file, streaming line by line. Returns entry tuples for batch insert."""
    entries = []
    session_id = file_path.stem
    project_dir = file_path.parent.name  # Opaque project ID (encoded form)
    idx = 0  # Track position of kept entries only

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                content_text = _extract_text(entry)
                entries.append(
                    (
                        str(file_path),
                        session_id,
                        project_dir,
                        entry.get("uuid"),
                        entry.get("type"),
                        entry.get("timestamp"),
                        content_text,
                        entry.get("model"),
                        entry.get("costUSD"),
                        line.strip(),
                        idx,  # Position in session
                    )
                )
                idx += 1
            except json.JSONDecodeError:
                continue
    return entries


def _parse_history(history_file: Path) -> list[tuple]:
    """Parse history.jsonl for user prompts."""
    entries = []
    idx = 0

    for line in history_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            display = entry.get("display", "")
            if not display.strip():
                continue

            entries.append(
                (
                    str(history_file),  # file_path
                    entry.get("sessionId", "history"),  # session_id
                    entry.get("project", ""),  # project_path
                    None,  # uuid
                    "prompt",  # type
                    entry.get("timestamp"),  # timestamp
                    display,  # content_text
                    None,  # model
                    None,  # cost_usd
                    line.strip(),  # raw_json
                    idx,  # idx
                )
            )
            idx += 1
        except json.JSONDecodeError:
            continue
    return entries


def sync(full: bool = False) -> dict:
    """Sync Claude transcripts to database. Uses file lock to prevent concurrent syncs."""
    with file_lock("claude"):
        conn = get_connection("claude")
        _init_schema(conn)
        conn.commit()  # Commit any schema changes before starting sync transaction

        try:
            conn.execute("BEGIN IMMEDIATE")

            if full:
                conn.execute("DELETE FROM entries")
                conn.execute("DELETE FROM tool_uses")
                conn.execute("DELETE FROM usage")
                conn.execute("DELETE FROM sync_meta")

            files = _find_files()
            existing_files = {str(f) for f in files}

            # Include history.jsonl in existing files set
            history_file = _get_claude_dir() / "history.jsonl"
            if history_file.exists():
                existing_files.add(str(history_file))

            stats = {"files": 0, "entries": 0, "skipped": 0, "deleted": 0}

            for file_path in files:
                if not full and not check_sync_needed(conn, file_path):
                    stats["skipped"] += 1
                    continue

                # Delete existing entries for this file
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

            # Also sync history.jsonl
            if history_file.exists() and (
                full or check_sync_needed(conn, history_file)
            ):
                conn.execute(
                    "DELETE FROM entries WHERE file_path = ?", (str(history_file),)
                )
                entries = _parse_history(history_file)
                if entries:
                    conn.executemany(
                        """
                        INSERT INTO entries (file_path, session_id, project_path, uuid, type,
                                           timestamp, content_text, model, cost_usd, raw_json, idx)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        entries,
                    )
                update_sync_meta(conn, history_file, len(entries))
                stats["files"] += 1
                stats["entries"] += len(entries)

            # Clean up entries for deleted files
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
    """Full-text search across Claude transcripts."""
    conn = get_connection("claude")
    _init_schema(conn)

    if not query:
        # Return recent entries if no query
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
    """Get Claude usage statistics."""
    conn = get_connection("claude")
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
