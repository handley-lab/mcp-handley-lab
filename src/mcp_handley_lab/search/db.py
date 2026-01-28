"""Unified database for transcript search.

Single SQLite DB with sessions, entries, sync_state tables.
FTS5 with external content triggers. Migration from legacy per-source DBs.
"""

import fcntl
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_NAME = "transcripts"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    session_key TEXT NOT NULL,
    display_name TEXT NOT NULL,
    project TEXT,
    entry_count INTEGER DEFAULT 0,
    first_ts REAL,
    last_ts REAL,
    UNIQUE(source, session_key)
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    idx INTEGER NOT NULL,
    role TEXT NOT NULL,
    timestamp_unix REAL,
    timestamp_text TEXT,
    content_text TEXT,
    model TEXT,
    cost_usd REAL,
    raw_json TEXT,
    UNIQUE(session_id, idx)
);

CREATE TABLE IF NOT EXISTS sync_state (
    source TEXT NOT NULL,
    session_key TEXT NOT NULL,
    mtime REAL,
    size INTEGER,
    tip_sha TEXT,
    entry_count INTEGER,
    PRIMARY KEY (source, session_key)
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    content_text, content='entries', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, content_text) VALUES (new.id, new.content_text);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid) VALUES('delete', old.id);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid) VALUES('delete', old.id);
    INSERT INTO entries_fts(rowid, content_text) VALUES (new.id, new.content_text);
END;

CREATE INDEX IF NOT EXISTS idx_entries_session_idx ON entries(session_id, idx);
CREATE INDEX IF NOT EXISTS idx_entries_role ON entries(role);
CREATE INDEX IF NOT EXISTS idx_entries_ts ON entries(timestamp_unix);
CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
"""


def get_search_dir() -> Path:
    """Get search database directory, respecting MCP_HANDLEY_LAB_MEMORY_DIR."""
    base = os.environ.get(
        "MCP_HANDLEY_LAB_MEMORY_DIR", str(Path.home() / ".mcp-handley-lab")
    )
    return Path(base) / "search"


def get_connection(db_name: str = DB_NAME) -> sqlite3.Connection:
    """Get database connection with performance pragmas."""
    search_dir = get_search_dir()
    search_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(search_dir / f"{db_name}.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize unified database schema."""
    conn.executescript(SCHEMA)


@contextmanager
def sync_lock():
    """Context manager for exclusive sync lock on the unified DB."""
    lock_path = get_search_dir() / f"{DB_NAME}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "w")  # noqa: SIM115
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError:
        raise RuntimeError("Sync already in progress") from None
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


# --- Session management ---


def get_or_create_session(
    conn: sqlite3.Connection,
    source: str,
    session_key: str,
    display_name: str,
    project: str | None,
) -> int:
    """Get existing session ID or create new one. Returns session.id."""
    row = conn.execute(
        "SELECT id FROM sessions WHERE source = ? AND session_key = ?",
        (source, session_key),
    ).fetchone()
    if row:
        # Update display_name and project in case they changed
        conn.execute(
            "UPDATE sessions SET display_name = ?, project = ? WHERE id = ?",
            (display_name, project, row["id"]),
        )
        return row["id"]
    cursor = conn.execute(
        """INSERT INTO sessions (source, session_key, display_name, project)
           VALUES (?, ?, ?, ?)""",
        (source, session_key, display_name, project),
    )
    return cursor.lastrowid


def update_session_stats(conn: sqlite3.Connection, session_id: int) -> None:
    """Update entry_count, first_ts, last_ts for a session."""
    conn.execute(
        """UPDATE sessions SET
               entry_count = (SELECT COUNT(*) FROM entries WHERE session_id = ?),
               first_ts = (SELECT MIN(timestamp_unix) FROM entries WHERE session_id = ?),
               last_ts = (SELECT MAX(timestamp_unix) FROM entries WHERE session_id = ?)
           WHERE id = ?""",
        (session_id, session_id, session_id, session_id),
    )


def delete_session_entries(conn: sqlite3.Connection, session_id: int) -> None:
    """Delete all entries for a session."""
    conn.execute("DELETE FROM entries WHERE session_id = ?", (session_id,))


# --- Sync state ---


def get_sync_fingerprint(
    conn: sqlite3.Connection, source: str, session_key: str
) -> str | None:
    """Get stored fingerprint for a sync item. Returns None if not tracked."""
    row = conn.execute(
        "SELECT mtime, size, tip_sha FROM sync_state WHERE source = ? AND session_key = ?",
        (source, session_key),
    ).fetchone()
    if not row:
        return None
    if row["tip_sha"]:
        return row["tip_sha"]
    return f"{row['mtime']}:{row['size']}"


def update_sync_state(
    conn: sqlite3.Connection,
    source: str,
    session_key: str,
    entry_count: int,
    mtime: float | None = None,
    size: int | None = None,
    tip_sha: str | None = None,
) -> None:
    """Update sync state for a session."""
    conn.execute(
        """INSERT OR REPLACE INTO sync_state (source, session_key, mtime, size, tip_sha, entry_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source, session_key, mtime, size, tip_sha, entry_count),
    )


def cleanup_stale_sessions(
    conn: sqlite3.Connection, source: str, active_keys: set[str]
) -> int:
    """Remove sessions and sync_state for items no longer discovered. Returns count."""
    rows = conn.execute(
        "SELECT session_key FROM sync_state WHERE source = ?", (source,)
    ).fetchall()
    deleted = 0
    for row in rows:
        if row["session_key"] not in active_keys:
            # Delete session (CASCADE deletes entries)
            conn.execute(
                "DELETE FROM sessions WHERE source = ? AND session_key = ?",
                (source, row["session_key"]),
            )
            conn.execute(
                "DELETE FROM sync_state WHERE source = ? AND session_key = ?",
                (source, row["session_key"]),
            )
            deleted += 1
    return deleted


# --- Entry insertion ---


def insert_entries(
    conn: sqlite3.Connection,
    session_id: int,
    entries: list[tuple],
) -> None:
    """Batch insert entries. Each tuple: (idx, role, timestamp_unix, timestamp_text,
    content_text, model, cost_usd, raw_json)."""
    conn.executemany(
        """INSERT INTO entries
           (session_id, idx, role, timestamp_unix, timestamp_text,
            content_text, model, cost_usd, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(session_id, *e) for e in entries],
    )


# --- Timestamp normalization ---


def parse_timestamp(ts_str: str | int | float | None) -> float | None:
    """Parse timestamp to unix epoch. Accepts ISO strings or epoch millis. Returns None on failure."""
    if ts_str is None:
        return None
    if isinstance(ts_str, int | float):
        # Epoch milliseconds (13+ digits) vs epoch seconds
        return ts_str / 1000 if ts_str > 1e12 else float(ts_str)
    if not ts_str:
        return None
    try:
        # Normalize Z suffix to +00:00 for fromisoformat compatibility
        ts = ts_str.replace("Z", "+00:00") if ts_str.endswith("Z") else ts_str
        if "T" in ts:
            # ISO 8601
            if "+" in ts[10:] or ts.count("-") > 2:
                # Has timezone offset
                dt = datetime.fromisoformat(ts)
            else:
                # Naive — assume UTC
                dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        else:
            # Date only
            dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


# --- Query functions ---


def fts_search(
    conn: sqlite3.Connection,
    query: str,
    source: str | None = None,
    limit: int = 20,
    project: str | None = None,
    role: str | None = None,
    since_unix: float | None = None,
    session_key: str | None = None,
) -> list[dict]:
    """FTS5 search with optional filters. Falls back to phrase search on syntax error.

    Returns dicts with entry fields plus session fields (source, session_key, display_name, project).
    Includes bm25 score for ranking.
    """

    def build_sql(fts_query: str) -> tuple[str, list]:
        sql = """
            SELECT e.*, s.source, s.session_key, s.display_name, s.project,
                   s.entry_count as session_entry_count,
                   bm25(entries_fts) as score
            FROM entries e
            JOIN entries_fts f ON e.id = f.rowid
            JOIN sessions s ON e.session_id = s.id
            WHERE entries_fts MATCH ?
        """
        params: list = [fts_query]

        if source:
            sql += " AND s.source = ?"
            params.append(source)
        if project:
            sql += " AND s.project LIKE ?"
            params.append(f"%{project}%")
        if role:
            sql += " AND e.role = ?"
            params.append(role)
        if since_unix is not None:
            sql += " AND e.timestamp_unix >= ?"
            params.append(since_unix)
        if session_key:
            sql += " AND s.session_key = ?"
            params.append(session_key)

        sql += " ORDER BY bm25(entries_fts) LIMIT ?"
        params.append(limit)
        return sql, params

    try:
        sql, params = build_sql(query)
        return [dict(row) for row in conn.execute(sql, params)]
    except sqlite3.OperationalError:
        safe_query = '"' + query.replace('"', '""') + '"'
        sql, params = build_sql(safe_query)
        return [dict(row) for row in conn.execute(sql, params)]


def search_recent(
    conn: sqlite3.Connection,
    source: str | None = None,
    limit: int = 20,
    project: str | None = None,
    role: str | None = None,
    since_unix: float | None = None,
    session_key: str | None = None,
) -> list[dict]:
    """Get recent entries (no FTS query). Returns same shape as fts_search."""
    sql = """
        SELECT e.*, s.source, s.session_key, s.display_name, s.project,
               s.entry_count as session_entry_count
        FROM entries e
        JOIN sessions s ON e.session_id = s.id
        WHERE 1=1
    """
    params: list = []

    if source:
        sql += " AND s.source = ?"
        params.append(source)
    if project:
        sql += " AND s.project LIKE ?"
        params.append(f"%{project}%")
    if role:
        sql += " AND e.role = ?"
        params.append(role)
    if since_unix is not None:
        sql += " AND e.timestamp_unix >= ?"
        params.append(since_unix)
    if session_key:
        sql += " AND s.session_key = ?"
        params.append(session_key)

    sql += " ORDER BY (e.timestamp_unix IS NULL), e.timestamp_unix DESC LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(sql, params)]


def slice_entries(
    conn: sqlite3.Connection,
    source: str,
    session_key: str,
    start: int = 0,
    end: int | None = None,
) -> list[dict]:
    """Get entries by position in session.

    Returns empty list for non-existent session or empty range.
    """
    start = max(0, start)
    if end is not None:
        end = max(0, end)
        if end <= start:
            return []

    sql = """
        SELECT e.*, s.source, s.session_key, s.display_name, s.project
        FROM entries e
        JOIN sessions s ON e.session_id = s.id
        WHERE s.source = ? AND s.session_key = ? AND e.idx >= ?
    """
    params: list = [source, session_key, start]
    if end is not None:
        sql += " AND e.idx < ?"
        params.append(end)
    sql += " ORDER BY e.idx"
    return [dict(row) for row in conn.execute(sql, params)]


def get_session_length(conn: sqlite3.Connection, source: str, session_key: str) -> int:
    """Get entry count for a session."""
    row = conn.execute(
        """SELECT entry_count FROM sessions
           WHERE source = ? AND session_key = ?""",
        (source, session_key),
    ).fetchone()
    return row["entry_count"] if row else 0


def get_sessions(
    conn: sqlite3.Connection, source: str | None = None, limit: int = 20
) -> list[dict]:
    """Get sessions with metadata, ordered by most recent activity."""
    sql = """
        SELECT source, session_key, display_name, project,
               entry_count, first_ts, last_ts
        FROM sessions
    """
    params: list = []
    if source:
        sql += " WHERE source = ?"
        params.append(source)
    sql += " ORDER BY (last_ts IS NULL) ASC, last_ts DESC LIMIT ?"
    params.append(limit)
    return [dict(row) for row in conn.execute(sql, params)]


def get_stats(conn: sqlite3.Connection, source: str | None = None) -> dict:
    """Get usage statistics, optionally filtered by source."""
    where = ""
    join_where = ""
    params: list = []
    if source:
        where = " WHERE s.source = ?"
        join_where = " AND s.source = ?"
        params = [source]

    totals = conn.execute(
        f"""SELECT COUNT(e.id) as entries,
                   COUNT(DISTINCT e.session_id) as sessions,
                   COUNT(DISTINCT s.project) as projects,
                   SUM(e.cost_usd) as total_cost
            FROM entries e
            JOIN sessions s ON e.session_id = s.id
            {where}""",
        params,
    ).fetchone()

    by_role = conn.execute(
        f"""SELECT e.role, COUNT(*) as count
            FROM entries e
            JOIN sessions s ON e.session_id = s.id
            WHERE 1=1 {join_where}
            GROUP BY e.role
            ORDER BY count DESC""",
        params,
    ).fetchall()

    return {
        "entries": totals["entries"],
        "sessions": totals["sessions"],
        "projects": totals["projects"],
        "total_cost": totals["total_cost"] or 0.0,
        "by_type": {row["role"]: row["count"] for row in by_role},
    }


# --- Migration from legacy DBs ---


def migrate_legacy_dbs(conn: sqlite3.Connection) -> dict[str, int]:
    """Import data from legacy per-source DBs into unified DB.

    Returns dict of {source: entries_imported}.
    """
    search_dir = get_search_dir()
    legacy_dbs = {
        "claude": search_dir / "claude.db",
        "codex": search_dir / "codex.db",
        "gemini": search_dir / "gemini.db",
        "mcp": search_dir / "mcp.db",
    }

    results = {}
    for source, db_path in legacy_dbs.items():
        if not db_path.exists():
            continue
        try:
            count = _import_legacy_db(conn, source, db_path)
            results[source] = count
            # Rename to .migrated
            migrated = Path(str(db_path) + ".migrated")
            db_path.rename(migrated)
            # Also rename WAL/SHM files if they exist
            for ext in ("-wal", "-shm"):
                wal = Path(str(db_path) + ext)
                if wal.exists():
                    wal.rename(Path(str(wal) + ".migrated"))
            logger.info("Migrated %d entries from %s", count, source)
        except Exception:
            logger.exception("Failed to migrate %s", source)
            results[source] = -1

    return results


def _import_legacy_db(conn: sqlite3.Connection, source: str, db_path: Path) -> int:
    """Import a single legacy DB. Returns entry count imported."""
    # Ensure no active transaction — ATTACH requires autocommit
    conn.commit()
    # SQLite doesn't support parameter binding for ATTACH, so quote the path
    safe_path = str(db_path).replace("'", "''")
    conn.execute(f"ATTACH DATABASE '{safe_path}' AS legacy")
    try:
        # Check if legacy DB has entries table
        has_entries = conn.execute(
            "SELECT name FROM legacy.sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        if not has_entries:
            return 0

        # Import sessions (derived from GROUP BY file_path)
        # Use REPLACE to strip directory, keeping just filename as display_name
        conn.execute(
            """INSERT OR IGNORE INTO sessions (source, session_key, display_name, project)
               SELECT ?,
                      le.file_path,
                      REPLACE(le.file_path,
                              RTRIM(le.file_path, REPLACE(le.file_path, '/', '')),
                              ''),
                      MAX(le.project_path)
               FROM legacy.entries le
               GROUP BY le.file_path""",
            (source,),
        )

        # Import entries with ROW_NUMBER to handle null/duplicate idx
        # OR IGNORE makes migration safe against partial reruns
        conn.execute(
            """INSERT OR IGNORE INTO entries (session_id, idx, role, timestamp_text,
                                              content_text, model, cost_usd, raw_json)
               SELECT s.id,
                      ROW_NUMBER() OVER (PARTITION BY le.file_path ORDER BY le.id) - 1,
                      le.type, le.timestamp,
                      le.content_text, le.model, le.cost_usd, le.raw_json
               FROM legacy.entries le
               JOIN sessions s ON s.source = ? AND s.session_key = le.file_path""",
            (source,),
        )
        entry_count = conn.execute("SELECT changes()").fetchone()[0]

        # Import sync_state
        has_sync = conn.execute(
            "SELECT name FROM legacy.sqlite_master WHERE type='table' AND name='sync_meta'"
        ).fetchone()
        if has_sync:
            # Check if sync_meta has tip_sha column (MCP memory)
            columns = {
                row[1] for row in conn.execute("PRAGMA legacy.table_info(sync_meta)")
            }
            if "tip_sha" in columns:
                conn.execute(
                    """INSERT OR IGNORE INTO sync_state
                       (source, session_key, tip_sha, entry_count)
                       SELECT ?, sm.file_path, sm.tip_sha, sm.entry_count
                       FROM legacy.sync_meta sm""",
                    (source,),
                )
            else:
                conn.execute(
                    """INSERT OR IGNORE INTO sync_state
                       (source, session_key, mtime, size, entry_count)
                       SELECT ?, sm.file_path, sm.mtime, sm.size, sm.entry_count
                       FROM legacy.sync_meta sm""",
                    (source,),
                )

        # Batch-compute timestamp_unix from timestamp_text
        _backfill_timestamps(conn)

        # Update session stats
        conn.execute(
            """UPDATE sessions SET
                   entry_count = (SELECT COUNT(*) FROM entries WHERE entries.session_id = sessions.id),
                   first_ts = (SELECT MIN(timestamp_unix) FROM entries WHERE entries.session_id = sessions.id),
                   last_ts = (SELECT MAX(timestamp_unix) FROM entries WHERE entries.session_id = sessions.id)
               WHERE source = ?""",
            (source,),
        )

        return entry_count
    finally:
        # Must commit before DETACH — SQLite requires no active transaction
        conn.commit()
        conn.execute("DETACH DATABASE legacy")


def _backfill_timestamps(conn: sqlite3.Connection) -> None:
    """Compute timestamp_unix for entries that have timestamp_text but no timestamp_unix."""
    rows = conn.execute(
        "SELECT id, timestamp_text FROM entries WHERE timestamp_unix IS NULL AND timestamp_text IS NOT NULL"
    ).fetchall()
    updates = []
    for row in rows:
        ts = parse_timestamp(row["timestamp_text"])
        if ts is not None:
            updates.append((ts, row["id"]))
    if updates:
        conn.executemany("UPDATE entries SET timestamp_unix = ? WHERE id = ?", updates)


def ensure_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Get or create unified DB connection, initialize schema, run migration if needed.

    This is the main entry point for getting a ready-to-use connection.
    """
    if conn is None:
        conn = get_connection()
    init_schema(conn)

    # Migrate legacy DBs only if unified DB is fresh (no sessions yet)
    has_data = conn.execute("SELECT 1 FROM sessions LIMIT 1").fetchone()
    if not has_data:
        search_dir = get_search_dir()
        legacy_exists = any(
            (search_dir / f"{name}.db").exists()
            for name in ("claude", "codex", "gemini", "mcp")
        )
        if legacy_exists:
            try:
                results = migrate_legacy_dbs(conn)
                conn.commit()
                if results:
                    logger.info("Migration complete: %s", results)
            except Exception:
                logger.exception("Migration failed, will resync from scratch")
                conn.rollback()

    return conn
