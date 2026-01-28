"""Unit tests for unified search database (db.py)."""

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_handley_lab.search import db


@pytest.fixture
def temp_search_dir(tmp_path):
    """Create a temporary search directory."""
    search_dir = tmp_path / "search"
    search_dir.mkdir()
    with patch.object(db, "get_search_dir", return_value=search_dir):
        yield search_dir


@pytest.fixture
def temp_db(temp_search_dir):
    """Create a temporary unified database with schema."""
    conn = db.get_connection()
    db.init_schema(conn)
    conn.commit()
    return conn


class TestGetSearchDir:
    def test_default_dir(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MCP_HANDLEY_LAB_MEMORY_DIR", None)
            search_dir = db.get_search_dir()
            assert search_dir == Path.home() / ".mcp-handley-lab" / "search"

    def test_custom_dir(self):
        with patch.dict(os.environ, {"MCP_HANDLEY_LAB_MEMORY_DIR": "/custom/path"}):
            search_dir = db.get_search_dir()
            assert search_dir == Path("/custom/path/search")


class TestGetConnection:
    def test_connection_creates_directory(self, temp_search_dir):
        conn = db.get_connection()
        assert temp_search_dir.exists()
        assert (temp_search_dir / "transcripts.db").exists()
        conn.close()

    def test_connection_has_row_factory(self, temp_search_dir):
        conn = db.get_connection()
        assert conn.row_factory == sqlite3.Row
        conn.close()


class TestSchema:
    def test_creates_sessions_table(self, temp_db):
        result = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        ).fetchone()
        assert result is not None

    def test_creates_entries_table(self, temp_db):
        result = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries'"
        ).fetchone()
        assert result is not None

    def test_creates_sync_state_table(self, temp_db):
        result = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_state'"
        ).fetchone()
        assert result is not None

    def test_creates_fts_table(self, temp_db):
        result = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries_fts'"
        ).fetchone()
        assert result is not None


class TestSessionManagement:
    def test_create_session(self, temp_db):
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/to/session.jsonl", "session-123", "project-a"
        )
        assert sid is not None
        assert sid > 0

    def test_get_existing_session(self, temp_db):
        sid1 = db.get_or_create_session(
            temp_db, "claude", "/path/to/session.jsonl", "session-123", "project-a"
        )
        sid2 = db.get_or_create_session(
            temp_db, "claude", "/path/to/session.jsonl", "session-123", "project-a"
        )
        assert sid1 == sid2

    def test_different_sources_different_sessions(self, temp_db):
        sid1 = db.get_or_create_session(
            temp_db, "claude", "/path/to/file", "name", None
        )
        sid2 = db.get_or_create_session(temp_db, "codex", "/path/to/file", "name", None)
        assert sid1 != sid2


class TestEntryOperations:
    def test_insert_and_retrieve(self, temp_db):
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            temp_db,
            sid,
            [
                (
                    0,
                    "user",
                    1704067200.0,
                    "2024-01-01T00:00:00Z",
                    "hello world",
                    None,
                    None,
                    None,
                ),
                (
                    1,
                    "assistant",
                    1704067201.0,
                    "2024-01-01T00:00:01Z",
                    "hi there",
                    "claude-3",
                    0.05,
                    None,
                ),
            ],
        )
        temp_db.commit()

        rows = temp_db.execute(
            "SELECT * FROM entries WHERE session_id = ?", (sid,)
        ).fetchall()
        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[0]["content_text"] == "hello world"
        assert rows[1]["role"] == "assistant"

    def test_fts_trigger_on_insert(self, temp_db):
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            temp_db,
            sid,
            [
                (
                    0,
                    "user",
                    None,
                    None,
                    "matplotlib plotting library",
                    None,
                    None,
                    None,
                ),
            ],
        )
        temp_db.commit()

        results = temp_db.execute(
            "SELECT * FROM entries_fts WHERE entries_fts MATCH 'matplotlib'"
        ).fetchall()
        assert len(results) == 1

    def test_fts_trigger_on_delete(self, temp_db):
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            temp_db,
            sid,
            [
                (0, "user", None, None, "unique_search_term", None, None, None),
            ],
        )
        temp_db.commit()

        # Verify findable
        results = db.fts_search(temp_db, "unique_search_term")
        assert len(results) == 1

        # Delete and verify gone
        db.delete_session_entries(temp_db, sid)
        temp_db.commit()

        results = db.fts_search(temp_db, "unique_search_term")
        assert len(results) == 0

    def test_update_session_stats(self, temp_db):
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            temp_db,
            sid,
            [
                (0, "user", 1704067200.0, None, "hello", None, None, None),
                (1, "assistant", 1704067201.0, None, "hi", None, None, None),
            ],
        )
        db.update_session_stats(temp_db, sid)
        temp_db.commit()

        row = temp_db.execute("SELECT * FROM sessions WHERE id = ?", (sid,)).fetchone()
        assert row["entry_count"] == 2
        assert row["first_ts"] == 1704067200.0
        assert row["last_ts"] == 1704067201.0


class TestFtsSearch:
    def _setup_entries(self, conn):
        sid = db.get_or_create_session(
            conn, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            conn,
            sid,
            [
                (
                    0,
                    "user",
                    None,
                    None,
                    "matplotlib plotting library",
                    None,
                    None,
                    None,
                ),
                (
                    1,
                    "assistant",
                    None,
                    None,
                    "numpy numerical computing",
                    None,
                    None,
                    None,
                ),
            ],
        )
        db.update_session_stats(conn, sid)
        conn.commit()
        return sid

    def test_basic_search(self, temp_db):
        self._setup_entries(temp_db)
        results = db.fts_search(temp_db, "matplotlib")
        assert len(results) == 1
        assert "matplotlib" in results[0]["content_text"]

    def test_prefix_search(self, temp_db):
        self._setup_entries(temp_db)
        results = db.fts_search(temp_db, "matplot*")
        assert len(results) == 1

    def test_filter_by_role(self, temp_db):
        self._setup_entries(temp_db)
        # Both have "library" or "computing" — search for something in both
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/session2.jsonl", "session-2", "project"
        )
        db.insert_entries(
            temp_db,
            sid,
            [
                (0, "user", None, None, "test query here", None, None, None),
                (1, "assistant", None, None, "test response here", None, None, None),
            ],
        )
        db.update_session_stats(temp_db, sid)
        temp_db.commit()

        results = db.fts_search(temp_db, "test", role="user")
        assert len(results) == 1
        assert results[0]["role"] == "user"

    def test_filter_by_source(self, temp_db):
        self._setup_entries(temp_db)
        results = db.fts_search(temp_db, "matplotlib", source="codex")
        assert len(results) == 0
        results = db.fts_search(temp_db, "matplotlib", source="claude")
        assert len(results) == 1

    def test_invalid_query_fallback(self, temp_db):
        self._setup_entries(temp_db)
        # Invalid FTS syntax should not raise
        results = db.fts_search(temp_db, "hello ( invalid")
        assert isinstance(results, list)

    def test_includes_bm25_score(self, temp_db):
        self._setup_entries(temp_db)
        results = db.fts_search(temp_db, "matplotlib")
        assert len(results) == 1
        assert "score" in results[0]
        assert isinstance(results[0]["score"], float)


class TestSliceEntries:
    def _setup_session(self, conn):
        sid = db.get_or_create_session(
            conn, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            conn,
            sid,
            [
                (
                    i,
                    "user" if i % 2 == 0 else "assistant",
                    None,
                    None,
                    f"entry {i}",
                    None,
                    None,
                    None,
                )
                for i in range(10)
            ],
        )
        db.update_session_stats(conn, sid)
        conn.commit()
        return sid

    def test_slice_range(self, temp_db):
        self._setup_session(temp_db)
        rows = db.slice_entries(
            temp_db, "claude", "/path/session.jsonl", start=2, end=5
        )
        assert len(rows) == 3
        assert rows[0]["idx"] == 2
        assert rows[2]["idx"] == 4

    def test_slice_from_start(self, temp_db):
        self._setup_session(temp_db)
        rows = db.slice_entries(
            temp_db, "claude", "/path/session.jsonl", start=0, end=3
        )
        assert len(rows) == 3

    def test_slice_to_end(self, temp_db):
        self._setup_session(temp_db)
        rows = db.slice_entries(temp_db, "claude", "/path/session.jsonl", start=8)
        assert len(rows) == 2

    def test_empty_range(self, temp_db):
        self._setup_session(temp_db)
        rows = db.slice_entries(
            temp_db, "claude", "/path/session.jsonl", start=5, end=5
        )
        assert len(rows) == 0

    def test_nonexistent_session(self, temp_db):
        rows = db.slice_entries(temp_db, "claude", "/nonexistent", start=0)
        assert len(rows) == 0


class TestSyncState:
    def test_new_item_no_fingerprint(self, temp_db):
        fp = db.get_sync_fingerprint(temp_db, "claude", "/path/new.jsonl")
        assert fp is None

    def test_filesystem_fingerprint(self, temp_db):
        db.update_sync_state(
            temp_db, "claude", "/path/file.jsonl", 10, mtime=12345.0, size=100
        )
        temp_db.commit()
        fp = db.get_sync_fingerprint(temp_db, "claude", "/path/file.jsonl")
        assert fp == "12345.0:100"

    def test_git_fingerprint(self, temp_db):
        db.update_sync_state(temp_db, "mcp", "/repo:main", 5, tip_sha="abc123")
        temp_db.commit()
        fp = db.get_sync_fingerprint(temp_db, "mcp", "/repo:main")
        assert fp == "abc123"


class TestCleanupStaleSessions:
    def test_removes_stale(self, temp_db):
        db.get_or_create_session(temp_db, "claude", "/path/a.jsonl", "a", None)
        db.get_or_create_session(temp_db, "claude", "/path/b.jsonl", "b", None)
        db.update_sync_state(temp_db, "claude", "/path/a.jsonl", 0)
        db.update_sync_state(temp_db, "claude", "/path/b.jsonl", 0)
        temp_db.commit()

        deleted = db.cleanup_stale_sessions(temp_db, "claude", {"/path/a.jsonl"})
        temp_db.commit()

        assert deleted == 1
        # a should still exist
        row = temp_db.execute(
            "SELECT * FROM sessions WHERE session_key = '/path/a.jsonl'"
        ).fetchone()
        assert row is not None
        # b should be gone
        row = temp_db.execute(
            "SELECT * FROM sessions WHERE session_key = '/path/b.jsonl'"
        ).fetchone()
        assert row is None


class TestSyncLock:
    def test_lock_creates_file(self, temp_search_dir):
        with db.sync_lock():
            assert (temp_search_dir / "transcripts.lock").exists()

    def test_lock_prevents_concurrent_access(self, temp_search_dir):
        with (  # noqa: SIM117
            db.sync_lock(),
            pytest.raises(RuntimeError, match="Sync already in progress"),
        ):
            with db.sync_lock():
                pass


class TestTimestampParsing:
    def test_iso_with_z(self):
        ts = db.parse_timestamp("2024-01-01T10:00:00Z")
        assert ts is not None
        assert isinstance(ts, float)
        # 2024-01-01T10:00:00 UTC = 1704103200.0
        assert ts == 1704103200.0

    def test_iso_with_offset(self):
        ts = db.parse_timestamp("2024-01-01T10:00:00+00:00")
        assert ts == 1704103200.0

    def test_iso_naive(self):
        ts = db.parse_timestamp("2024-01-01T10:00:00")
        assert ts is not None

    def test_date_only(self):
        ts = db.parse_timestamp("2024-01-01")
        assert ts is not None

    def test_none_returns_none(self):
        assert db.parse_timestamp(None) is None

    def test_invalid_returns_none(self):
        assert db.parse_timestamp("not-a-date") is None

    def test_empty_returns_none(self):
        assert db.parse_timestamp("") is None


class TestGetSessions:
    def test_returns_sessions(self, temp_db):
        db.get_or_create_session(
            temp_db, "claude", "/path/a.jsonl", "session-a", "project"
        )
        db.get_or_create_session(
            temp_db, "codex", "/path/b.jsonl", "session-b", "project2"
        )
        temp_db.commit()

        all_sessions = db.get_sessions(temp_db)
        assert len(all_sessions) == 2

        claude_sessions = db.get_sessions(temp_db, source="claude")
        assert len(claude_sessions) == 1
        assert claude_sessions[0]["source"] == "claude"


class TestGetStats:
    def test_returns_stats(self, temp_db):
        sid = db.get_or_create_session(
            temp_db, "claude", "/path/session.jsonl", "session-1", "project"
        )
        db.insert_entries(
            temp_db,
            sid,
            [
                (0, "user", None, None, "hello", None, None, None),
                (1, "assistant", None, None, "hi", None, 0.05, None),
            ],
        )
        db.update_session_stats(temp_db, sid)
        temp_db.commit()

        stats = db.get_stats(temp_db, "claude")
        assert stats["entries"] == 2
        assert stats["sessions"] == 1
        assert stats["projects"] == 1
        assert stats["total_cost"] == 0.05
        assert stats["by_type"]["user"] == 1
        assert stats["by_type"]["assistant"] == 1

    def test_filtered_by_source(self, temp_db):
        sid1 = db.get_or_create_session(temp_db, "claude", "/a", "a", None)
        sid2 = db.get_or_create_session(temp_db, "codex", "/b", "b", None)
        db.insert_entries(
            temp_db,
            sid1,
            [
                (0, "user", None, None, "hello", None, None, None),
            ],
        )
        db.insert_entries(
            temp_db,
            sid2,
            [
                (0, "user", None, None, "hello", None, None, None),
                (1, "assistant", None, None, "hi", None, None, None),
            ],
        )
        temp_db.commit()

        claude_stats = db.get_stats(temp_db, "claude")
        assert claude_stats["entries"] == 1

        codex_stats = db.get_stats(temp_db, "codex")
        assert codex_stats["entries"] == 2


class TestLegacyMigration:
    """Test migration from legacy per-source DBs."""

    def _create_legacy_db(self, path, entries, sync_entries=None):
        """Create a minimal legacy DB with entries table."""
        conn = sqlite3.connect(str(path))
        conn.execute(
            """CREATE TABLE entries (
                id INTEGER PRIMARY KEY,
                file_path TEXT,
                session_id TEXT,
                project_path TEXT,
                idx INTEGER,
                type TEXT,
                timestamp TEXT,
                content_text TEXT,
                model TEXT,
                cost_usd REAL,
                raw_json TEXT
            )"""
        )
        for entry in entries:
            conn.execute(
                """INSERT INTO entries
                   (file_path, session_id, project_path, idx, type, timestamp, content_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                entry,
            )
        if sync_entries:
            conn.execute(
                """CREATE TABLE sync_meta (
                    file_path TEXT PRIMARY KEY,
                    mtime REAL,
                    size INTEGER,
                    entry_count INTEGER
                )"""
            )
            for se in sync_entries:
                conn.execute(
                    "INSERT INTO sync_meta (file_path, mtime, size, entry_count) VALUES (?, ?, ?, ?)",
                    se,
                )
        conn.commit()
        conn.close()

    def test_basic_migration(self, temp_search_dir):
        """Test migrating a legacy DB with entries."""
        legacy_path = temp_search_dir / "claude.db"
        self._create_legacy_db(
            legacy_path,
            [
                (
                    "/path/to/session.jsonl",
                    "session-1",
                    "/project",
                    0,
                    "user",
                    "2024-01-01T10:00:00Z",
                    "hello",
                ),
                (
                    "/path/to/session.jsonl",
                    "session-1",
                    "/project",
                    1,
                    "assistant",
                    "2024-01-01T10:00:01Z",
                    "hi",
                ),
            ],
        )

        conn = db.get_connection()
        db.init_schema(conn)
        conn.commit()

        results = db.migrate_legacy_dbs(conn)
        conn.commit()

        assert results["claude"] == 2

        # Check sessions created correctly
        sessions = conn.execute(
            "SELECT * FROM sessions WHERE source = 'claude'"
        ).fetchall()
        assert len(sessions) == 1
        assert sessions[0]["session_key"] == "/path/to/session.jsonl"
        assert sessions[0]["display_name"] == "session.jsonl"

        # Check entries imported with correct idx
        entries = conn.execute(
            "SELECT idx, role, content_text FROM entries ORDER BY idx"
        ).fetchall()
        assert len(entries) == 2
        assert entries[0]["idx"] == 0
        assert entries[1]["idx"] == 1
        assert entries[0]["role"] == "user"

        # Legacy DB should be renamed
        assert not legacy_path.exists()
        assert Path(str(legacy_path) + ".migrated").exists()

    def test_migration_null_idx(self, temp_search_dir):
        """Test migration handles null idx by generating ROW_NUMBER."""
        legacy_path = temp_search_dir / "claude.db"
        self._create_legacy_db(
            legacy_path,
            [
                ("/path/s.jsonl", "s1", None, None, "user", None, "first"),
                ("/path/s.jsonl", "s1", None, None, "assistant", None, "second"),
                ("/path/s.jsonl", "s1", None, None, "user", None, "third"),
            ],
        )

        conn = db.get_connection()
        db.init_schema(conn)
        conn.commit()

        results = db.migrate_legacy_dbs(conn)
        conn.commit()

        assert results["claude"] == 3

        # All idx should be unique (0, 1, 2)
        idxs = [
            row[0]
            for row in conn.execute("SELECT idx FROM entries ORDER BY idx").fetchall()
        ]
        assert idxs == [0, 1, 2]

    def test_migration_with_sync_meta(self, temp_search_dir):
        """Test migration imports sync_state."""
        legacy_path = temp_search_dir / "claude.db"
        self._create_legacy_db(
            legacy_path,
            [("/path/s.jsonl", "s1", None, 0, "user", None, "hello")],
            sync_entries=[("/path/s.jsonl", 1234.5, 100, 1)],
        )

        conn = db.get_connection()
        db.init_schema(conn)
        conn.commit()

        db.migrate_legacy_dbs(conn)
        conn.commit()

        sync = conn.execute(
            "SELECT * FROM sync_state WHERE source = 'claude'"
        ).fetchone()
        assert sync is not None
        assert sync["mtime"] == 1234.5
        assert sync["size"] == 100

    def test_migration_idempotent(self, temp_search_dir):
        """Test that migration doesn't run if unified DB already has data."""
        # First create some data in unified DB
        conn = db.get_connection()
        db.init_schema(conn)
        sid = db.get_or_create_session(conn, "claude", "/existing", "existing", None)
        db.insert_entries(
            conn,
            sid,
            [
                (0, "user", None, None, "existing data", None, None, None),
            ],
        )
        conn.commit()

        # Create a legacy DB
        legacy_path = temp_search_dir / "claude.db"
        self._create_legacy_db(
            legacy_path,
            [
                ("/path/s.jsonl", "s1", None, 0, "user", None, "legacy data"),
            ],
        )

        # ensure_db should NOT migrate because sessions already has data
        db.ensure_db()
        # Legacy DB should still exist (not renamed)
        assert legacy_path.exists()

    def test_migration_double_run_safe(self, temp_search_dir):
        """Test that running migration twice doesn't fail or duplicate entries."""
        legacy_path = temp_search_dir / "claude.db"
        self._create_legacy_db(
            legacy_path,
            [
                ("/path/s.jsonl", "s1", None, 0, "user", None, "hello"),
                ("/path/s.jsonl", "s1", None, 1, "assistant", None, "hi"),
            ],
        )

        conn = db.get_connection()
        db.init_schema(conn)
        conn.commit()

        # First migration
        results1 = db.migrate_legacy_dbs(conn)
        conn.commit()
        assert results1["claude"] == 2

        # Recreate legacy DB (simulate partial failure that didn't rename)
        self._create_legacy_db(
            legacy_path,
            [
                ("/path/s.jsonl", "s1", None, 0, "user", None, "hello"),
                ("/path/s.jsonl", "s1", None, 1, "assistant", None, "hi"),
            ],
        )

        # Second migration should not fail (INSERT OR IGNORE)
        results2 = db.migrate_legacy_dbs(conn)
        conn.commit()
        # Should report counts but not actually duplicate
        assert results2["claude"] >= 0  # No error (-1)

        # Verify no duplicates
        count = conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]
        assert count == 2
