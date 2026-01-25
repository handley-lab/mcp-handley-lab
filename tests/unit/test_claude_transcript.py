"""Unit tests for Claude Code data access module."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from mcp_handley_lab.claude import (
    github_repos,
    history,
    mcp_servers,
    project_stats,
    projects,
    sessions,
    skill_usage,
    transcript,
)
from mcp_handley_lab.claude.transcript import _extract_message, _get_project_dir


class TestProjectDirEncoding:
    """Test project directory path encoding."""

    def test_encode_simple_path(self):
        """Test encoding of simple path."""
        with patch("os.getcwd", return_value="/home/user/code"):
            project_dir = _get_project_dir()
            assert project_dir.name == "-home-user-code"

    def test_encode_path_with_dots(self):
        """Test encoding of path with dots."""
        project_dir = _get_project_dir("/home/user/tmp/mcp.1")
        assert project_dir.name == "-home-user-tmp-mcp-1"

    def test_encode_explicit_path(self):
        """Test encoding with explicit path parameter."""
        project_dir = _get_project_dir("/home/will/code/blackjax")
        assert project_dir.name == "-home-will-code-blackjax"


class TestSessions:
    """Test sessions() function."""

    def test_sessions_no_index_file(self):
        """Test sessions returns empty list when no index file exists."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(Path, "home", return_value=Path(tmpdir)),
        ):
            result = sessions("/some/project")
            assert result == []

    def test_sessions_with_index(self):
        """Test sessions returns entries from index file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            project_dir = tmppath / ".claude" / "projects" / "-test-project"
            project_dir.mkdir(parents=True)

            index_data = {
                "version": 1,
                "entries": [
                    {
                        "sessionId": "abc123",
                        "summary": "Test session",
                        "messageCount": 5,
                    }
                ],
            }
            (project_dir / "sessions-index.json").write_text(json.dumps(index_data))

            with patch.object(Path, "home", return_value=tmppath):
                result = sessions("/test/project")
                assert len(result) == 1
                assert result[0]["sessionId"] == "abc123"


class TestTranscript:
    """Test transcript() function."""

    def test_transcript_no_files(self):
        """Test transcript returns empty list when no files exist."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(Path, "home", return_value=Path(tmpdir)),
        ):
            result = transcript(project_path="/some/project")
            assert result == []

    def test_transcript_user_assistant_only(self):
        """Test transcript filters to user/assistant messages by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            project_dir = tmppath / ".claude" / "projects" / "-test-project"
            project_dir.mkdir(parents=True)

            lines = [
                json.dumps({"type": "system", "subtype": "init"}),
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "Hello"},
                        "timestamp": "2024-01-01T00:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "type": "assistant",
                        "message": {"role": "assistant", "content": "Hi there"},
                        "timestamp": "2024-01-01T00:00:01Z",
                    }
                ),
            ]
            (project_dir / "session123.jsonl").write_text("\n".join(lines))

            with patch.object(Path, "home", return_value=tmppath):
                result = transcript(project_path="/test/project")
                assert len(result) == 2
                assert result[0]["type"] == "user"
                assert result[1]["type"] == "assistant"

    def test_transcript_raw_mode(self):
        """Test transcript returns all entries in raw mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            project_dir = tmppath / ".claude" / "projects" / "-test-project"
            project_dir.mkdir(parents=True)

            lines = [
                json.dumps({"type": "system", "subtype": "init"}),
                json.dumps({"type": "user", "message": {"content": "Hello"}}),
            ]
            (project_dir / "session123.jsonl").write_text("\n".join(lines))

            with patch.object(Path, "home", return_value=tmppath):
                result = transcript(project_path="/test/project", raw=True)
                assert len(result) == 2
                assert result[0]["type"] == "system"

    def test_transcript_specific_session(self):
        """Test transcript reads specific session by ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            project_dir = tmppath / ".claude" / "projects" / "-test-project"
            project_dir.mkdir(parents=True)

            (project_dir / "abc123.jsonl").write_text(
                json.dumps({"type": "user", "message": {"content": "Session A"}})
            )
            (project_dir / "xyz789.jsonl").write_text(
                json.dumps({"type": "user", "message": {"content": "Session B"}})
            )

            with patch.object(Path, "home", return_value=tmppath):
                result = transcript(session_id="abc123", project_path="/test/project")
                assert len(result) == 1
                assert result[0]["content"] == "Session A"


class TestExtractMessage:
    """Test _extract_message() function."""

    def test_extract_simple_string_content(self):
        """Test extraction of simple string content."""
        entry = {
            "type": "user",
            "message": {"role": "user", "content": "Hello world"},
            "timestamp": "2024-01-01T00:00:00Z",
        }
        result = _extract_message(entry)
        assert result["type"] == "user"
        assert result["role"] == "user"
        assert result["content"] == "Hello world"
        assert result["timestamp"] == "2024-01-01T00:00:00Z"

    def test_extract_array_content(self):
        """Test extraction of array content with text blocks."""
        entry = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First part."},
                    {"type": "tool_use", "id": "123", "name": "Read"},
                    {"type": "text", "text": "Second part."},
                ],
            },
            "timestamp": "2024-01-01T00:00:00Z",
        }
        result = _extract_message(entry)
        assert result["type"] == "assistant"
        assert result["content"] == "First part.\nSecond part."

    def test_extract_missing_content(self):
        """Test extraction handles missing content gracefully."""
        entry = {"type": "user", "timestamp": "2024-01-01T00:00:00Z"}
        result = _extract_message(entry)
        assert result["type"] == "user"
        assert "content" not in result or result.get("content") is None


class TestHistory:
    """Test history() function."""

    def test_history_no_file(self):
        """Test history returns empty list when file doesn't exist."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(Path, "home", return_value=Path(tmpdir)),
        ):
            result = history()
            assert result == []

    def test_history_basic(self):
        """Test history reads prompt entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / ".claude").mkdir()

            lines = [
                json.dumps(
                    {
                        "display": "First prompt",
                        "timestamp": 1000,
                        "project": "/proj1",
                        "sessionId": "s1",
                    }
                ),
                json.dumps(
                    {
                        "display": "Second prompt",
                        "timestamp": 2000,
                        "project": "/proj2",
                        "sessionId": "s2",
                    }
                ),
            ]
            (tmppath / ".claude" / "history.jsonl").write_text("\n".join(lines))

            with patch.object(Path, "home", return_value=tmppath):
                result = history()
                assert len(result) == 2
                assert result[0]["display"] == "First prompt"
                assert result[1]["project"] == "/proj2"
                assert "pastedContents" not in result[0]

    def test_history_with_pasted_content(self):
        """Test history includes pasted content when requested."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / ".claude").mkdir()

            entry = {
                "display": "Review this code",
                "timestamp": 1000,
                "project": "/proj",
                "sessionId": "s1",
                "pastedContents": {
                    "1": {"id": 1, "type": "text", "content": "def foo(): pass"}
                },
            }
            (tmppath / ".claude" / "history.jsonl").write_text(json.dumps(entry))

            with patch.object(Path, "home", return_value=tmppath):
                result = history(include_pasted=True)
                assert len(result) == 1
                assert "pastedContents" in result[0]
                assert result[0]["pastedContents"]["1"]["content"] == "def foo(): pass"


class TestState:
    """Test state.py functions."""

    def test_projects_empty(self):
        """Test projects returns empty dict when file doesn't exist."""
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            patch.object(Path, "home", return_value=Path(tmpdir)),
        ):
            result = projects()
            assert result == {}

    def test_projects_with_data(self):
        """Test projects returns project data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data = {
                "projects": {
                    "/home/user/proj1": {"lastCost": 1.5, "lastLinesAdded": 10},
                    "/home/user/proj2": {"lastCost": 2.5, "lastLinesAdded": 20},
                }
            }
            (tmppath / ".claude.json").write_text(json.dumps(data))

            with patch.object(Path, "home", return_value=tmppath):
                result = projects()
                assert len(result) == 2
                assert result["/home/user/proj1"]["lastCost"] == 1.5

    def test_project_stats_current_cwd(self):
        """Test project_stats returns stats for current working directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data = {"projects": {"/current/cwd": {"lastCost": 3.0}}}
            (tmppath / ".claude.json").write_text(json.dumps(data))

            with (
                patch.object(Path, "home", return_value=tmppath),
                patch("os.getcwd", return_value="/current/cwd"),
            ):
                result = project_stats()
                assert result["lastCost"] == 3.0

    def test_project_stats_explicit_path(self):
        """Test project_stats with explicit path parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data = {"projects": {"/explicit/path": {"lastCost": 5.0}}}
            (tmppath / ".claude.json").write_text(json.dumps(data))

            with patch.object(Path, "home", return_value=tmppath):
                result = project_stats("/explicit/path")
                assert result["lastCost"] == 5.0

    def test_github_repos(self):
        """Test github_repos returns repo mappings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data = {"githubRepoPaths": {"owner/repo": ["/local/path1", "/local/path2"]}}
            (tmppath / ".claude.json").write_text(json.dumps(data))

            with patch.object(Path, "home", return_value=tmppath):
                result = github_repos()
                assert "owner/repo" in result
                assert len(result["owner/repo"]) == 2

    def test_mcp_servers(self):
        """Test mcp_servers returns server configurations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data = {"mcpServers": {"email": {"type": "stdio", "command": "mcp-email"}}}
            (tmppath / ".claude.json").write_text(json.dumps(data))

            with patch.object(Path, "home", return_value=tmppath):
                result = mcp_servers()
                assert "email" in result
                assert result["email"]["command"] == "mcp-email"

    def test_skill_usage(self):
        """Test skill_usage returns usage statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            data = {
                "skillUsage": {"arxiv": {"usageCount": 7, "lastUsedAt": 1769276074252}}
            }
            (tmppath / ".claude.json").write_text(json.dumps(data))

            with patch.object(Path, "home", return_value=tmppath):
                result = skill_usage()
                assert "arxiv" in result
                assert result["arxiv"]["usageCount"] == 7
