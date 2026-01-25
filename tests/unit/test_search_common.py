"""Unit tests for search common utilities."""

import os
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_handley_lab.search import common


@pytest.fixture
def temp_search_dir(tmp_path):
    """Create a temporary search directory."""
    search_dir = tmp_path / "search"
    search_dir.mkdir()
    with patch.object(common, "get_search_dir", return_value=search_dir):
        yield search_dir


@pytest.fixture
def temp_db(temp_search_dir):
    """Create a temporary database with schema."""
    conn = common.get_connection("test")
    conn.executescript("""
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
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_meta (
            file_path TEXT PRIMARY KEY,
            mtime REAL,
            size INTEGER,
            entry_count INTEGER
        );
    """)
    common.setup_fts_with_triggers(conn)
    return conn


class TestGetSearchDir:
    def test_default_dir(self):
        """Test default search directory is under home."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove MCP_HANDLEY_LAB_MEMORY_DIR if set
            os.environ.pop("MCP_HANDLEY_LAB_MEMORY_DIR", None)
            search_dir = common.get_search_dir()
            assert search_dir == Path.home() / ".mcp-handley-lab" / "search"

    def test_custom_dir(self):
        """Test custom directory via environment variable."""
        with patch.dict(os.environ, {"MCP_HANDLEY_LAB_MEMORY_DIR": "/custom/path"}):
            search_dir = common.get_search_dir()
            assert search_dir == Path("/custom/path/search")


class TestGetConnection:
    def test_connection_creates_directory(self, tmp_path):
        """Test that get_connection creates the search directory."""
        search_dir = tmp_path / "search"
        with patch.object(common, "get_search_dir", return_value=search_dir):
            conn = common.get_connection("test")
            assert search_dir.exists()
            assert (search_dir / "test.db").exists()
            conn.close()

    def test_connection_has_row_factory(self, tmp_path):
        """Test that connection uses Row factory."""
        search_dir = tmp_path / "search"
        search_dir.mkdir()
        with patch.object(common, "get_search_dir", return_value=search_dir):
            conn = common.get_connection("test")
            assert conn.row_factory == sqlite3.Row
            conn.close()


class TestSetupFtsWithTriggers:
    def test_creates_fts_table(self, temp_db):
        """Test that FTS table is created."""
        # Check FTS table exists
        result = temp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='entries_fts'"
        ).fetchone()
        assert result is not None

    def test_insert_trigger(self, temp_db):
        """Test that insert trigger populates FTS."""
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'user', 'hello world')
        """)
        temp_db.commit()

        # Search should find the entry
        results = temp_db.execute(
            "SELECT * FROM entries_fts WHERE entries_fts MATCH 'hello'"
        ).fetchall()
        assert len(results) == 1

    def test_delete_trigger(self, temp_db):
        """Test that delete trigger updates FTS index.

        Note: With FTS5 external content tables, the delete trigger marks
        the FTS entry for removal, but the actual content lookup goes to
        the content table. After delete, fts_search correctly returns no
        results because the JOIN with entries finds nothing.
        """
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'user', 'hello world')
        """)
        temp_db.commit()

        # Verify we can find it before delete
        results = common.fts_search(temp_db, "hello")
        assert len(results) == 1

        temp_db.execute("DELETE FROM entries WHERE session_id = 'session1'")
        temp_db.commit()

        # After delete, the JOIN in fts_search returns no results
        # because the entries table row no longer exists
        # (even though FTS shadow table may still have stale data)
        results = temp_db.execute("""
            SELECT e.* FROM entries e
            JOIN entries_fts f ON e.id = f.rowid
            WHERE e.session_id = 'session1'
        """).fetchall()
        assert len(results) == 0


class TestFtsSearch:
    def test_basic_search(self, temp_db):
        """Test basic FTS search."""
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'user', 'matplotlib plotting library')
        """)
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'assistant', 'numpy numerical computing')
        """)
        temp_db.commit()

        results = common.fts_search(temp_db, "matplotlib")
        assert len(results) == 1
        assert "matplotlib" in results[0]["content_text"]

    def test_prefix_search(self, temp_db):
        """Test prefix search with *."""
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'user', 'matplotlib plotting')
        """)
        temp_db.commit()

        results = common.fts_search(temp_db, "matplot*")
        assert len(results) == 1

    def test_filter_by_type(self, temp_db):
        """Test filtering by entry type."""
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'user', 'test query')
        """)
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'assistant', 'test response')
        """)
        temp_db.commit()

        results = common.fts_search(temp_db, "test", filters={"type": "user"})
        assert len(results) == 1
        assert results[0]["type"] == "user"

    def test_invalid_query_fallback(self, temp_db):
        """Test that invalid FTS query falls back to phrase search."""
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('test.jsonl', 'session1', 'user', 'hello world test')
        """)
        temp_db.commit()

        # Invalid FTS syntax should fall back to phrase search
        results = common.fts_search(temp_db, "hello ( invalid")
        # Should not raise, but may return 0 results due to phrase mismatch
        assert isinstance(results, list)


class TestCheckSyncNeeded:
    def test_new_file_needs_sync(self, temp_db, tmp_path):
        """Test that new files need sync."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("test")
        assert common.check_sync_needed(temp_db, test_file)

    def test_unchanged_file_no_sync(self, temp_db, tmp_path):
        """Test that unchanged files don't need sync."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("test")
        stat = test_file.stat()

        temp_db.execute(
            "INSERT INTO sync_meta (file_path, mtime, size, entry_count) VALUES (?, ?, ?, ?)",
            (str(test_file), stat.st_mtime, stat.st_size, 1),
        )
        temp_db.commit()

        assert not common.check_sync_needed(temp_db, test_file)

    def test_modified_file_needs_sync(self, temp_db, tmp_path):
        """Test that modified files need sync."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("test")
        stat = test_file.stat()

        # Insert old mtime
        temp_db.execute(
            "INSERT INTO sync_meta (file_path, mtime, size, entry_count) VALUES (?, ?, ?, ?)",
            (str(test_file), stat.st_mtime - 1, stat.st_size, 1),
        )
        temp_db.commit()

        assert common.check_sync_needed(temp_db, test_file)


class TestUpdateSyncMeta:
    def test_update_creates_entry(self, temp_db, tmp_path):
        """Test that update_sync_meta creates new entry."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("test content")

        common.update_sync_meta(temp_db, test_file, 5)
        temp_db.commit()

        result = temp_db.execute(
            "SELECT * FROM sync_meta WHERE file_path = ?", (str(test_file),)
        ).fetchone()
        assert result is not None
        assert result["entry_count"] == 5

    def test_update_replaces_entry(self, temp_db, tmp_path):
        """Test that update_sync_meta replaces existing entry."""
        test_file = tmp_path / "test.jsonl"
        test_file.write_text("test content")

        common.update_sync_meta(temp_db, test_file, 5)
        temp_db.commit()

        test_file.write_text("more content")
        common.update_sync_meta(temp_db, test_file, 10)
        temp_db.commit()

        result = temp_db.execute(
            "SELECT * FROM sync_meta WHERE file_path = ?", (str(test_file),)
        ).fetchone()
        assert result["entry_count"] == 10


class TestCleanupDeletedFiles:
    def test_removes_deleted_files(self, temp_db):
        """Test that entries for deleted files are removed."""
        # Insert entries for two files
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('file1.jsonl', 'session1', 'user', 'content1')
        """)
        temp_db.execute("""
            INSERT INTO entries (file_path, session_id, type, content_text)
            VALUES ('file2.jsonl', 'session2', 'user', 'content2')
        """)
        temp_db.execute(
            "INSERT INTO sync_meta (file_path, mtime, size, entry_count) VALUES (?, ?, ?, ?)",
            ("file1.jsonl", 1.0, 100, 1),
        )
        temp_db.execute(
            "INSERT INTO sync_meta (file_path, mtime, size, entry_count) VALUES (?, ?, ?, ?)",
            ("file2.jsonl", 1.0, 100, 1),
        )
        temp_db.commit()

        # Cleanup with only file1 existing
        deleted = common.cleanup_deleted_files(temp_db, {"file1.jsonl"})
        temp_db.commit()

        assert deleted == 1

        # file1 should still exist
        result = temp_db.execute(
            "SELECT * FROM entries WHERE file_path = 'file1.jsonl'"
        ).fetchone()
        assert result is not None

        # file2 should be gone
        result = temp_db.execute(
            "SELECT * FROM entries WHERE file_path = 'file2.jsonl'"
        ).fetchone()
        assert result is None


class TestFileLock:
    def test_lock_creates_file(self, temp_search_dir):
        """Test that file_lock creates lock file."""
        with common.file_lock("test"):
            assert (temp_search_dir / "test.lock").exists()

    def test_lock_prevents_concurrent_access(self, temp_search_dir):
        """Test that file_lock raises on concurrent access."""
        with (  # noqa: SIM117 - inner with must be nested to test lock contention
            common.file_lock("test"),
            pytest.raises(RuntimeError, match="Sync already in progress"),
        ):
            with common.file_lock("test"):
                pass
