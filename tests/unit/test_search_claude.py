"""Unit tests for Claude Code search source adapter and end-to-end sync."""

import json
from unittest.mock import patch

import pytest

from mcp_handley_lab.search import db
from mcp_handley_lab.search.core import context
from mcp_handley_lab.search.models import SyncItem
from mcp_handley_lab.search.sources import claude
from mcp_handley_lab.search.sync import sync_single_source


@pytest.fixture
def temp_search_dir(tmp_path):
    """Create a temporary search directory."""
    search_dir = tmp_path / "search"
    search_dir.mkdir()
    with patch.object(db, "get_search_dir", return_value=search_dir):
        yield search_dir


@pytest.fixture
def temp_db(temp_search_dir):
    """Create a temporary unified database."""
    conn = db.get_connection()
    db.init_schema(conn)
    conn.commit()
    return conn


@pytest.fixture
def temp_claude_dir(tmp_path):
    """Create a temporary Claude directory with sample data."""
    claude_dir = tmp_path / ".claude"
    projects_dir = claude_dir / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    session_file = projects_dir / "session-123.jsonl"
    entries = [
        {
            "uuid": "1",
            "type": "user",
            "timestamp": "2024-01-01T10:00:00Z",
            "message": {"content": "How do I use matplotlib?"},
        },
        {
            "uuid": "2",
            "type": "assistant",
            "timestamp": "2024-01-01T10:00:01Z",
            "message": {
                "content": [
                    {"type": "text", "text": "Here is how to use matplotlib:"},
                    {"type": "text", "text": "import matplotlib.pyplot as plt"},
                ]
            },
            "model": "claude-3-opus",
            "costUSD": 0.05,
        },
        {
            "uuid": "3",
            "type": "system",
            "timestamp": "2024-01-01T10:00:02Z",
            "content": "System message",
        },
        {
            "uuid": "4",
            "type": "summary",
            "timestamp": "2024-01-01T10:00:03Z",
            "summary": "User asked about matplotlib",
        },
    ]
    with open(session_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    return claude_dir


class TestExtractText:
    def test_user_message_string(self):
        entry = {
            "type": "user",
            "message": {"content": "hello world"},
        }
        text = claude._extract_text(entry)
        assert text == "hello world"

    def test_user_message_list(self):
        entry = {
            "type": "user",
            "message": {
                "content": [
                    {"type": "text", "text": "line 1"},
                    {"type": "text", "text": "line 2"},
                ]
            },
        }
        text = claude._extract_text(entry)
        assert "line 1" in text
        assert "line 2" in text

    def test_assistant_with_thinking(self):
        entry = {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Let me think..."},
                    {"type": "text", "text": "Here is my answer"},
                ]
            },
        }
        text = claude._extract_text(entry)
        assert "Let me think" in text
        assert "Here is my answer" in text

    def test_assistant_with_tool_use(self):
        entry = {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Read",
                        "input": {"file_path": "/path/to/file.py"},
                    }
                ]
            },
        }
        text = claude._extract_text(entry)
        assert "tool:Read" in text
        assert "/path/to/file.py" in text

    def test_tool_result_string(self):
        entry = {
            "type": "assistant",
            "toolUseResult": "file contents here",
            "message": {"content": ""},
        }
        text = claude._extract_text(entry)
        assert "file contents here" in text

    def test_tool_result_list(self):
        entry = {
            "type": "assistant",
            "toolUseResult": [{"type": "text", "text": "result 1"}],
            "message": {"content": ""},
        }
        text = claude._extract_text(entry)
        assert "result 1" in text

    def test_system_message(self):
        entry = {"type": "system", "content": "system prompt"}
        text = claude._extract_text(entry)
        assert text == "system prompt"

    def test_summary_message(self):
        entry = {"type": "summary", "summary": "conversation summary"}
        text = claude._extract_text(entry)
        assert text == "conversation summary"


class TestDiscoverItems:
    def test_finds_files(self, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            items = claude.discover_items()
        assert len(items) == 1
        assert items[0].display_name == "session-123"
        assert items[0].project == "test-project"

    def test_excludes_agent_files(self, temp_claude_dir):
        projects_dir = temp_claude_dir / "projects" / "test-project"
        agent_file = projects_dir / "agent-123.jsonl"
        agent_file.write_text('{"type": "user", "message": {"content": "test"}}')

        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            items = claude.discover_items()
        assert not any("agent-" in i.session_key for i in items)

    def test_includes_history(self, temp_claude_dir):
        history = temp_claude_dir / "history.jsonl"
        history.write_text(
            json.dumps(
                {
                    "display": "test prompt",
                    "timestamp": "2024-01-01T10:00:00Z",
                }
            )
            + "\n"
        )

        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            items = claude.discover_items()
        assert any(i.display_name == "history" for i in items)


class TestLoadEntries:
    def test_parses_entries(self, temp_claude_dir):
        session_file = (
            temp_claude_dir / "projects" / "test-project" / "session-123.jsonl"
        )
        item = SyncItem(
            session_key=str(session_file),
            display_name="session-123",
            project="test-project",
            fingerprint="0:0",
        )
        entries = claude.load_entries(item)
        assert len(entries) == 4
        assert entries[0].role == "user"
        assert "matplotlib" in entries[0].content
        assert entries[0].idx == 0
        assert entries[1].idx == 1

    def test_handles_invalid_json(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text(
            '{"valid": "json", "type": "system", "content": "ok"}\ninvalid json\n'
        )
        item = SyncItem(
            session_key=str(f), display_name="test", project=None, fingerprint="0:0"
        )
        entries = claude.load_entries(item)
        # Should parse the valid line, skip the invalid one
        assert len(entries) >= 1


class TestEndToEndSync:
    """Test sync through the shared orchestration layer."""

    def test_full_sync(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            stats = sync_single_source("claude", claude, full=True)

        assert stats["files"] == 1
        assert stats["entries"] == 4
        assert stats["skipped"] == 0

    def test_incremental_sync_skips_unchanged(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            sync_single_source("claude", claude, full=True)
            stats = sync_single_source("claude", claude, full=False)

        assert stats["skipped"] == 1
        assert stats["files"] == 0

    def test_search_after_sync(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            sync_single_source("claude", claude, full=True)

        conn = db.get_connection()
        db.init_schema(conn)
        results = db.fts_search(conn, "matplotlib", source="claude")
        assert len(results) > 0
        assert any("matplotlib" in r["content_text"] for r in results)

    def test_search_by_role(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            sync_single_source("claude", claude, full=True)

        conn = db.get_connection()
        db.init_schema(conn)
        results = db.search_recent(conn, source="claude", role="user", limit=100)
        assert all(r["role"] == "user" for r in results)

    def test_search_empty_query(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            sync_single_source("claude", claude, full=True)

        conn = db.get_connection()
        db.init_schema(conn)
        results = db.search_recent(conn, source="claude", limit=10)
        assert len(results) > 0

    def test_stats_after_sync(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            sync_single_source("claude", claude, full=True)

        conn = db.get_connection()
        db.init_schema(conn)
        stats = db.get_stats(conn, "claude")
        assert stats["entries"] == 4
        assert stats["sessions"] == 1
        assert stats["projects"] == 1
        assert "by_type" in stats
        assert stats["by_type"]["user"] == 1


class TestCoreContextAPI:
    """Test the core context() function with structured outputs (Phase 2)."""

    def _sync(self, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            sync_single_source("claude", claude, full=True)

    def test_search_returns_structured_hits(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        result = context(action="search", source="claude", query="matplotlib")
        assert isinstance(result, dict)
        assert "hits" in result
        assert "total" in result
        assert "query" in result
        assert result["total"] > 0
        hit = result["hits"][0]
        assert "session_id" in hit
        assert "entry_index" in hit
        assert "session_length" in hit
        assert "role" in hit
        assert "snippet" in hit
        assert "source" in hit
        assert hit["source"] == "claude"
        assert hit["session_id"].startswith("claude:")

    def test_search_has_bm25_score(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        result = context(action="search", source="claude", query="matplotlib")
        hit = result["hits"][0]
        assert "score" in hit
        assert hit["score"] is not None
        assert isinstance(hit["score"], float)

    def test_search_empty_returns_dict(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        result = context(action="search", source="claude", query="")
        assert isinstance(result, dict)
        assert "hits" in result
        assert result["total"] > 0

    def test_slice_returns_structured(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        # Get session_id from search
        search = context(action="search", source="claude", query="matplotlib")
        session_id = search["hits"][0]["session_id"]

        result = context(action="slice", source="claude", file_path=session_id)
        assert isinstance(result, dict)
        assert "session_id" in result
        assert "source" in result
        assert "entry_count" in result
        assert "entries" in result
        assert result["session_id"] == session_id
        assert result["source"] == "claude"
        assert len(result["entries"]) > 0
        entry = result["entries"][0]
        assert "entry_index" in entry
        assert "role" in entry
        assert "content" in entry

    def test_slice_with_max_chars(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        search = context(action="search", source="claude", query="matplotlib")
        session_id = search["hits"][0]["session_id"]

        result = context(
            action="slice", source="claude", file_path=session_id, max_chars=10
        )
        for entry in result["entries"]:
            # Entries with content should respect max_chars (+ "...")
            if entry["content"]:
                assert len(entry["content"]) <= 13  # 10 + "..."

    def test_sessions_returns_structured(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        result = context(action="sessions", source="claude")
        assert isinstance(result, dict)
        assert "source" in result
        assert "sessions" in result
        assert result["source"] == "claude"
        session = result["sessions"][0]
        assert "session_id" in session
        assert "display_name" in session
        assert "entry_count" in session
        assert session["session_id"].startswith("claude:")

    def test_stats_returns_dict(self, temp_search_dir, temp_claude_dir):
        self._sync(temp_claude_dir)
        result = context(action="stats", source="claude")
        assert isinstance(result, dict)
        assert "entries" in result
        assert "sessions" in result

    def test_sync_returns_dict(self, temp_search_dir, temp_claude_dir):
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            result = context(action="sync", source="claude", full=True)
        assert isinstance(result, dict)
        assert "files" in result
        assert "entries" in result

    def test_composite_session_id_roundtrip(self, temp_search_dir, temp_claude_dir):
        """Search → get session_id → slice with it → verify consistency."""
        self._sync(temp_claude_dir)
        search = context(action="search", source="claude", query="matplotlib")
        session_id = search["hits"][0]["session_id"]

        # Slice using composite session_id
        sliced = context(action="slice", source="claude", file_path=session_id)
        assert sliced["session_id"] == session_id

        # Sessions should also have same session_id format
        sessions = context(action="sessions", source="claude")
        session_ids = [s["session_id"] for s in sessions["sessions"]]
        assert session_id in session_ids
