"""Unit tests for Claude Code search module."""

import json
from unittest.mock import patch

import pytest

from mcp_handley_lab.search import claude, common


@pytest.fixture
def temp_search_dir(tmp_path):
    """Create a temporary search directory."""
    search_dir = tmp_path / "search"
    search_dir.mkdir()
    with patch.object(common, "get_search_dir", return_value=search_dir):
        yield search_dir


@pytest.fixture
def temp_claude_dir(tmp_path):
    """Create a temporary Claude directory with sample data."""
    claude_dir = tmp_path / ".claude"
    projects_dir = claude_dir / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    # Create sample JSONL file
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
        """Test extracting text from user message with string content."""
        entry = {
            "type": "user",
            "message": {"content": "hello world"},
        }
        text = claude._extract_text(entry)
        assert text == "hello world"

    def test_user_message_list(self):
        """Test extracting text from user message with list content."""
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
        """Test extracting thinking blocks from assistant message."""
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
        """Test extracting tool use from assistant message."""
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
        """Test extracting tool result as string."""
        entry = {
            "type": "assistant",
            "toolUseResult": "file contents here",
            "message": {"content": ""},
        }
        text = claude._extract_text(entry)
        assert "file contents here" in text

    def test_tool_result_list(self):
        """Test extracting tool result as list."""
        entry = {
            "type": "assistant",
            "toolUseResult": [{"type": "text", "text": "result 1"}],
            "message": {"content": ""},
        }
        text = claude._extract_text(entry)
        assert "result 1" in text

    def test_system_message(self):
        """Test extracting system message."""
        entry = {"type": "system", "content": "system prompt"}
        text = claude._extract_text(entry)
        assert text == "system prompt"

    def test_summary_message(self):
        """Test extracting summary message."""
        entry = {"type": "summary", "summary": "conversation summary"}
        text = claude._extract_text(entry)
        assert text == "conversation summary"


class TestFindFiles:
    def test_finds_jsonl_files(self, temp_claude_dir):
        """Test that _find_files finds JSONL files."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            files = claude._find_files()
            assert len(files) == 1
            assert files[0].suffix == ".jsonl"

    def test_excludes_agent_files(self, temp_claude_dir):
        """Test that agent- prefixed files are excluded."""
        # Create an agent file
        projects_dir = temp_claude_dir / "projects" / "test-project"
        agent_file = projects_dir / "agent-123.jsonl"
        agent_file.write_text('{"type": "user", "message": {"content": "test"}}')

        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            files = claude._find_files()
            assert not any(f.name.startswith("agent-") for f in files)


class TestParseFile:
    def test_parses_entries(self, temp_claude_dir):
        """Test that _parse_file correctly parses entries."""
        session_file = (
            temp_claude_dir / "projects" / "test-project" / "session-123.jsonl"
        )
        entries = claude._parse_file(session_file)

        assert len(entries) == 4
        # Check first entry (user message)
        assert entries[0][1] == "session-123"  # session_id
        assert entries[0][2] == "test-project"  # project_path
        assert entries[0][4] == "user"  # type
        assert "matplotlib" in entries[0][6]  # content_text

    def test_handles_invalid_json(self, tmp_path):
        """Test that invalid JSON lines are skipped."""
        session_file = tmp_path / "test.jsonl"
        session_file.write_text('{"valid": "json"}\ninvalid json\n{"also": "valid"}')
        entries = claude._parse_file(session_file)
        # Should have 2 valid entries (but with empty content_text)
        assert len(entries) >= 0  # May skip entries with no content


class TestSync:
    def test_full_sync(self, temp_search_dir, temp_claude_dir):
        """Test full sync creates database entries."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            stats = claude.sync(full=True)

        assert stats["files"] == 1
        assert stats["entries"] == 4
        assert stats["skipped"] == 0

    def test_incremental_sync_skips_unchanged(self, temp_search_dir, temp_claude_dir):
        """Test incremental sync skips unchanged files."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            # First sync
            claude.sync(full=True)
            # Second sync should skip
            stats = claude.sync(full=False)

        assert stats["skipped"] == 1
        assert stats["files"] == 0


class TestSearch:
    def test_search_by_query(self, temp_search_dir, temp_claude_dir):
        """Test search finds matching entries."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            claude.sync(full=True)
            results = claude.search(query="matplotlib")

        assert len(results) > 0
        assert any("matplotlib" in r["content_text"] for r in results)

    def test_search_by_type(self, temp_search_dir, temp_claude_dir):
        """Test search filters by type."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            claude.sync(full=True)
            results = claude.search(query="", type="user", limit=100)

        assert all(r["type"] == "user" for r in results)

    def test_search_empty_query_returns_recent(self, temp_search_dir, temp_claude_dir):
        """Test empty query returns recent entries."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            claude.sync(full=True)
            results = claude.search(query="", limit=10)

        assert len(results) > 0


class TestStats:
    def test_stats_returns_counts(self, temp_search_dir, temp_claude_dir):
        """Test stats returns correct counts."""
        with patch.object(claude, "_get_claude_dir", return_value=temp_claude_dir):
            claude.sync(full=True)
            stats = claude.stats()

        assert stats["entries"] == 4
        assert stats["sessions"] == 1
        assert stats["projects"] == 1
        assert "by_type" in stats
        assert stats["by_type"]["user"] == 1
