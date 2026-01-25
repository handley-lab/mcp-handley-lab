"""Shared utilities for transcript search modules."""

import fcntl
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def get_search_dir() -> Path:
    """Get search database directory, respecting MCP_HANDLEY_LAB_MEMORY_DIR."""
    base = os.environ.get(
        "MCP_HANDLEY_LAB_MEMORY_DIR", str(Path.home() / ".mcp-handley-lab")
    )
    return Path(base) / "search"


def get_connection(db_name: str) -> sqlite3.Connection:
    """Get database connection with performance pragmas."""
    search_dir = get_search_dir()
    search_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(search_dir / f"{db_name}.db")
    conn.row_factory = sqlite3.Row
    # Performance pragmas for bulk operations
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    return conn


def setup_fts_with_triggers(conn: sqlite3.Connection, table: str = "entries"):
    """Create FTS5 table with insert/delete triggers for automatic sync."""
    conn.executescript(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {table}_fts USING fts5(
            content_text, content='{table}', content_rowid='id'
        );

        -- Canonical FTS5 external-content trigger patterns
        CREATE TRIGGER IF NOT EXISTS {table}_ai AFTER INSERT ON {table} BEGIN
            INSERT INTO {table}_fts(rowid, content_text) VALUES (new.id, new.content_text);
        END;

        CREATE TRIGGER IF NOT EXISTS {table}_ad AFTER DELETE ON {table} BEGIN
            INSERT INTO {table}_fts({table}_fts, rowid) VALUES('delete', old.id);
        END;

        CREATE TRIGGER IF NOT EXISTS {table}_au AFTER UPDATE ON {table} BEGIN
            INSERT INTO {table}_fts({table}_fts, rowid) VALUES('delete', old.id);
            INSERT INTO {table}_fts(rowid, content_text) VALUES (new.id, new.content_text);
        END;
    """)


def fts_search(
    conn: sqlite3.Connection,
    query: str,
    table: str = "entries",
    limit: int = 20,
    filters: dict | None = None,
) -> list[dict]:
    """Execute FTS search with optional filters. Falls back to phrase search on syntax error."""

    def build_sql(fts_query: str) -> tuple[str, list]:
        sql = f"""
            SELECT e.* FROM {table} e
            JOIN {table}_fts f ON e.id = f.rowid
            WHERE {table}_fts MATCH ?
        """
        params: list = [fts_query]

        if filters:
            if filters.get("project_path"):
                sql += " AND e.project_path LIKE ?"
                params.append(f"%{filters['project_path']}%")
            if filters.get("type"):
                sql += " AND e.type = ?"
                params.append(filters["type"])
            if filters.get("timestamp"):
                sql += " AND e.timestamp >= ?"
                params.append(filters["timestamp"])

        sql += f" ORDER BY bm25({table}_fts) LIMIT ?"
        params.append(limit)
        return sql, params

    # Try raw query first (supports AND, OR, NEAR, prefix *)
    try:
        sql, params = build_sql(query)
        return [dict(row) for row in conn.execute(sql, params)]
    except sqlite3.OperationalError:
        # Fall back to safe phrase search
        safe_query = '"' + query.replace('"', '""') + '"'
        sql, params = build_sql(safe_query)
        return [dict(row) for row in conn.execute(sql, params)]


def check_sync_needed(conn: sqlite3.Connection, file_path: Path) -> bool:
    """Check if file needs re-syncing based on mtime AND size."""
    row = conn.execute(
        "SELECT mtime, size FROM sync_meta WHERE file_path = ?", (str(file_path),)
    ).fetchone()
    if not row:
        return True
    stat = file_path.stat()
    return stat.st_mtime > row["mtime"] or stat.st_size != row["size"]


def update_sync_meta(
    conn: sqlite3.Connection, file_path: Path, entry_count: int
) -> None:
    """Update sync metadata for a file."""
    stat = file_path.stat()
    conn.execute(
        """
        INSERT OR REPLACE INTO sync_meta (file_path, mtime, size, entry_count)
        VALUES (?, ?, ?, ?)
        """,
        (str(file_path), stat.st_mtime, stat.st_size, entry_count),
    )


def cleanup_deleted_files(conn: sqlite3.Connection, existing_files: set[str]) -> int:
    """Remove entries for files that no longer exist. Returns count of deleted files."""
    rows = conn.execute("SELECT file_path FROM sync_meta").fetchall()
    deleted = 0
    for row in rows:
        if row["file_path"] not in existing_files:
            conn.execute("DELETE FROM entries WHERE file_path = ?", (row["file_path"],))
            conn.execute(
                "DELETE FROM sync_meta WHERE file_path = ?", (row["file_path"],)
            )
            deleted += 1
    return deleted


def ensure_idx_column(conn: sqlite3.Connection) -> bool:
    """Ensure idx column exists. Returns True if migration was performed.

    This auto-migrates existing DBs by adding the idx column and forcing
    a resync (by clearing sync_meta) so that idx gets populated during parsing.
    """
    columns = {row[1] for row in conn.execute("PRAGMA table_info(entries)")}
    if "idx" not in columns:
        conn.execute("ALTER TABLE entries ADD COLUMN idx INTEGER")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_file_idx ON entries(file_path, idx)"
        )
        # Force resync by clearing sync_meta - ensures idx gets populated
        conn.execute("DELETE FROM sync_meta")
        return True
    return False


def slice_entries(
    conn: sqlite3.Connection,
    file_path: str,
    start: int = 0,
    end: int | None = None,
) -> list[dict]:
    """Get entries by position in session.

    Args:
        file_path: Unique session identifier (session_id can collide)
        start: Start index (0-indexed), negative values clamped to 0
        end: End index (exclusive), None = to end of session
             Negative values clamped to 0 (returns empty)

    Returns empty list for non-existent file_path or empty range.
    """
    start = max(0, start)  # Clamp negative start
    if end is not None:
        end = max(0, end)  # Clamp negative end
        if end <= start:
            return []  # Empty range

    # Use COALESCE for robustness against any NULL idx (shouldn't happen after migration)
    sql = "SELECT * FROM entries WHERE file_path = ? AND COALESCE(idx, 0) >= ?"
    params: list = [file_path, start]
    if end is not None:
        sql += " AND COALESCE(idx, 0) < ?"
        params.append(end)
    sql += " ORDER BY COALESCE(idx, 0)"
    return [dict(row) for row in conn.execute(sql, params)]


def get_sessions(conn: sqlite3.Connection) -> list[dict]:
    """Get all sessions with metadata.

    Groups by file_path (the unique session identity).
    Uses MIN(session_id) for deterministic results.
    """
    sql = """
        SELECT
            file_path,
            MIN(session_id) as session_id,
            COALESCE(MAX(project_path), MIN(project_path)) as project_path,
            MIN(timestamp) as start_time,
            MAX(timestamp) as end_time,
            COUNT(*) as entry_count
        FROM entries
        GROUP BY file_path
        ORDER BY (end_time IS NULL) ASC, end_time DESC
    """
    return [dict(row) for row in conn.execute(sql)]


def get_session_length(conn: sqlite3.Connection, file_path: str) -> int:
    """Get entry count for a session (identified by file_path)."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM entries WHERE file_path = ?", (file_path,)
    ).fetchone()
    return row["cnt"] if row else 0


@contextmanager
def file_lock(db_name: str):
    """Context manager for exclusive sync lock. Prevents concurrent sync operations."""
    lock_path = get_search_dir() / f"{db_name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "w")  # noqa: SIM115 - kept open for flock duration
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise RuntimeError(f"Sync already in progress for {db_name}") from None
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
