"""Integration tests for Otter.ai tool with VCR recording."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import vcr

from mcp_handley_lab.otter.shared import _clear_session_cache
from mcp_handley_lab.otter.tool import mcp

otter_vcr = vcr.VCR(
    serializer="yaml",
    cassette_library_dir=str(Path(__file__).parent / "otter_cassettes"),
    record_mode="once",
    match_on=["method", "scheme", "host", "port", "path", "query"],
    filter_headers=["cookie"],
    decode_compressed_response=True,
)


@pytest.fixture(autouse=True)
def _reset_otter_session():
    """Reset cached httpx client between tests."""
    _clear_session_cache()
    yield
    _clear_session_cache()


@pytest.fixture
def mock_session(tmp_path):
    """Create a mock session file with dummy cookies.

    For recording cassettes, set OTTER_SESSION_FILE to a real session file.
    For replay, dummy cookies suffice since VCR intercepts HTTP.
    """
    real_session = os.environ.get("OTTER_SESSION_FILE")
    if real_session and Path(real_session).exists():
        session_file = Path(real_session)
    else:
        session_file = tmp_path / "session.json"
        session_file.write_text(
            json.dumps(
                {
                    "cookies": [
                        {
                            "name": "sessionid",
                            "value": "test-session-id",
                            "domain": ".otter.ai",
                            "path": "/",
                        },
                        {
                            "name": "csrftoken",
                            "value": "test-csrf-token",
                            "domain": ".otter.ai",
                            "path": "/",
                        },
                    ],
                    "refreshed_at": "2026-01-01T00:00:00",
                }
            )
        )
    with patch(
        "mcp_handley_lab.otter.shared.settings.otter_session_file",
        str(session_file),
    ):
        yield session_file


@pytest.mark.integration
class TestOtterIntegration:
    """Integration tests for Otter.ai MCP tool."""

    @otter_vcr.use_cassette("test_recent_meetings.yaml")
    @pytest.mark.asyncio
    async def test_recent_meetings(self, mock_session):
        """List recent meetings."""
        _, response = await mcp.call_tool(
            "otter",
            {"action": "recent", "limit": 3},
        )
        assert "meetings" in response
        meetings = response["meetings"]
        assert isinstance(meetings, list)
        for meeting in meetings:
            assert "otid" in meeting
            assert "title" in meeting

    @otter_vcr.use_cassette("test_search_meetings.yaml")
    @pytest.mark.asyncio
    async def test_search_meetings(self, mock_session):
        """Search meetings by title."""
        _, response = await mcp.call_tool(
            "otter",
            {"action": "search", "query": "test"},
        )
        assert "meetings" in response
        meetings = response["meetings"]
        assert isinstance(meetings, list)

    @otter_vcr.use_cassette("test_live_meetings.yaml")
    @pytest.mark.asyncio
    async def test_live_meetings(self, mock_session):
        """List live meetings (may return empty list)."""
        _, response = await mcp.call_tool(
            "otter",
            {"action": "live"},
        )
        assert "meetings" in response
        assert isinstance(response["meetings"], list)

    @otter_vcr.use_cassette("test_transcript.yaml")
    @pytest.mark.asyncio
    async def test_transcript(self, mock_session):
        """Get a transcript by otid."""
        _, response = await mcp.call_tool(
            "otter",
            {"action": "transcript", "otid": "AOJlmcqnR1OC6ZhzTYmO2J0c5ak"},
        )
        assert "transcript" in response
        transcript = response["transcript"]
        assert transcript["otid"] == "AOJlmcqnR1OC6ZhzTYmO2J0c5ak"
        assert "segments" in transcript
        assert "formatted_text" in transcript
        assert "speakers" in transcript

    @otter_vcr.use_cassette("test_transcript_max_segments.yaml")
    @pytest.mark.asyncio
    async def test_transcript_max_segments(self, mock_session):
        """Get a transcript with max_segments truncation."""
        _, response = await mcp.call_tool(
            "otter",
            {
                "action": "transcript",
                "otid": "AOJlmcqnR1OC6ZhzTYmO2J0c5ak",
                "max_segments": 3,
            },
        )
        assert "transcript" in response
        segments = response["transcript"]["segments"]
        assert len(segments) <= 3


@pytest.mark.integration
class TestOtterValidation:
    """Test input validation via MCP protocol."""

    @pytest.mark.asyncio
    async def test_transcript_requires_otid(self, mock_session):
        """Transcript action without otid raises error."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="otid"):
            await mcp.call_tool("otter", {"action": "transcript"})

    @pytest.mark.asyncio
    async def test_search_requires_query(self, mock_session):
        """Search action without query raises error."""
        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="query"):
            await mcp.call_tool("otter", {"action": "search"})
