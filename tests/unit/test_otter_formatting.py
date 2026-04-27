"""Unit tests for Otter.ai transcript formatting and parsing logic."""

from unittest.mock import patch

from mcp_handley_lab.otter.shared import (
    MeetingSummary,
    OtterResult,
    TranscriptResult,
    _format_transcript,
    _parse_meeting,
    get_transcript,
)


class TestParsesMeeting:
    """Test _parse_meeting with various API response shapes."""

    def test_full_meeting(self):
        raw = {
            "otid": "abc123",
            "title": "Team Standup",
            "created_at": 1700000000,
            "live_status": "ended",
        }
        result = _parse_meeting(raw)
        assert result == MeetingSummary(
            otid="abc123",
            title="Team Standup",
            created_at=1700000000,
            live_status="ended",
        )

    def test_minimal_meeting(self):
        raw = {"otid": "xyz789"}
        result = _parse_meeting(raw)
        assert result is not None
        assert result.otid == "xyz789"
        assert result.title == ""
        assert result.created_at == 0

    def test_missing_otid_returns_none(self):
        raw = {"title": "No ID"}
        assert _parse_meeting(raw) is None

    def test_none_input_returns_none(self):
        assert _parse_meeting(None) is None


class TestFormatTranscript:
    """Test _format_transcript with various segment shapes."""

    def test_basic_formatting(self):
        transcripts = [
            {"transcript": "Hello everyone", "start_offset": 0, "speaker_id": 1},
            {"transcript": "Hi there", "start_offset": 5000, "speaker_id": 2},
        ]
        speakers = {1: "Alice", 2: "Bob"}
        text, segments = _format_transcript(transcripts, speakers)

        assert "[00:00] **Alice**: Hello everyone" in text
        assert "[00:05] **Bob**: Hi there" in text
        assert len(segments) == 2
        assert segments[0].speaker_name == "Alice"
        assert segments[1].speaker_name == "Bob"

    def test_sorts_by_offset(self):
        transcripts = [
            {"transcript": "Second", "start_offset": 10000, "speaker_id": 1},
            {"transcript": "First", "start_offset": 5000, "speaker_id": 1},
        ]
        speakers = {1: "Alice"}
        text, segments = _format_transcript(transcripts, speakers)

        assert segments[0].text == "First"
        assert segments[1].text == "Second"

    def test_stable_sort_tiebreaker(self):
        """Segments with same offset preserve original order."""
        transcripts = [
            {"transcript": "A", "start_offset": 0, "speaker_id": 1},
            {"transcript": "B", "start_offset": 0, "speaker_id": 1},
        ]
        speakers = {1: "Alice"}
        _, segments = _format_transcript(transcripts, speakers)
        assert segments[0].text == "A"
        assert segments[1].text == "B"

    def test_skips_empty_segments(self):
        transcripts = [
            {"transcript": "Real content", "start_offset": 0, "speaker_id": 1},
            {"transcript": "", "start_offset": 1000, "speaker_id": 1},
            {"transcript": "   ", "start_offset": 2000, "speaker_id": 1},
        ]
        speakers = {1: "Alice"}
        _, segments = _format_transcript(transcripts, speakers)
        assert len(segments) == 1

    def test_unknown_speaker_id(self):
        transcripts = [
            {"transcript": "Hello", "start_offset": 0, "speaker_id": 99},
        ]
        speakers = {1: "Alice"}
        _, segments = _format_transcript(transcripts, speakers)
        assert segments[0].speaker_name == "Speaker 99"

    def test_null_speaker_id(self):
        transcripts = [
            {"transcript": "Hello", "start_offset": 0, "speaker_id": None},
        ]
        speakers = {1: "Alice"}
        _, segments = _format_transcript(transcripts, speakers)
        assert segments[0].speaker_name == "Unknown"

    def test_missing_speaker_id(self):
        transcripts = [
            {"transcript": "Hello", "start_offset": 0},
        ]
        speakers = {1: "Alice"}
        _, segments = _format_transcript(transcripts, speakers)
        assert segments[0].speaker_name == "Unknown"

    def test_time_formatting(self):
        transcripts = [
            {"transcript": "At 1:30", "start_offset": 90000, "speaker_id": 1},
        ]
        speakers = {1: "Alice"}
        text, _ = _format_transcript(transcripts, speakers)
        assert "[01:30] **Alice**: At 1:30" in text

    def test_empty_input(self):
        text, segments = _format_transcript([], {})
        assert text == ""
        assert segments == []


class TestOtterResultSerialization:
    """Test OtterResult envelope excludes None fields."""

    def test_meetings_only(self):
        result = OtterResult(meetings=[MeetingSummary(otid="abc", title="Test")])
        data = result.model_dump()
        assert "meetings" in data
        assert "transcript" not in data
        assert "refresh" not in data

    def test_empty_meetings_list_included(self):
        result = OtterResult(meetings=[])
        data = result.model_dump()
        assert "meetings" in data
        assert data["meetings"] == []


class TestTranscriptResultSerialization:
    """Test TranscriptResult omits None formatted_text."""

    def test_formatted_text_none_omitted(self):
        result = TranscriptResult(otid="abc", formatted_text=None)
        data = result.model_dump()
        assert "formatted_text" not in data

    def test_formatted_text_present_included(self):
        result = TranscriptResult(otid="abc", formatted_text="some text")
        data = result.model_dump()
        assert data["formatted_text"] == "some text"

    def test_formatted_text_empty_string_included(self):
        result = TranscriptResult(otid="abc", formatted_text="")
        data = result.model_dump()
        assert "formatted_text" in data
        assert data["formatted_text"] == ""


# Mock data for get_transcript tests
_MOCK_SPEECH = {
    "speech": {
        "title": "Test Meeting",
        "live_status": "ended",
        "created_at": 1700000000,
        "transcripts": [
            {"transcript": "First", "start_offset": 1000, "speaker_id": 1},
            {"transcript": "Second", "start_offset": 5000, "speaker_id": 1},
            {"transcript": "Third", "start_offset": 10000, "speaker_id": 2},
            {"transcript": "Fourth", "start_offset": 20000, "speaker_id": 2},
            {"transcript": "Fifth", "start_offset": 30000, "speaker_id": 1},
        ],
    }
}
_MOCK_SPEAKERS = {
    "speakers": [{"id": 1, "speaker_name": "Alice"}, {"id": 2, "speaker_name": "Bob"}]
}


def _patch_api(speech=_MOCK_SPEECH, speakers=_MOCK_SPEAKERS):
    """Patch _api_get to return mock data for get_transcript tests."""

    def fake_api_get(path, params=None):
        if path == "speech":
            return speech
        if path == "speakers":
            return speakers
        raise ValueError(f"Unexpected path: {path}")

    return patch("mcp_handley_lab.otter.shared._api_get", side_effect=fake_api_get)


class TestGetTranscriptSinceOffset:
    """Test since_offset_ms filtering in get_transcript."""

    def test_default_returns_all(self):
        with _patch_api():
            result = get_transcript("test-otid")
        assert len(result.segments) == 5

    def test_since_offset_filters(self):
        with _patch_api():
            result = get_transcript("test-otid", since_offset_ms=5000)
        # Should exclude segments at offset <= 5000 (1000 and 5000)
        assert len(result.segments) == 3
        assert result.segments[0].text == "Third"
        assert result.segments[0].start_offset_ms == 10000

    def test_since_offset_zero_returns_all(self):
        with _patch_api():
            result = get_transcript("test-otid", since_offset_ms=0)
        assert len(result.segments) == 5

    def test_since_offset_beyond_all_returns_empty(self):
        with _patch_api():
            result = get_transcript("test-otid", since_offset_ms=99999)
        assert len(result.segments) == 0
        assert result.formatted_text == ""

    def test_include_formatted_text_false(self):
        with _patch_api():
            result = get_transcript("test-otid", include_formatted_text=False)
        assert len(result.segments) == 5
        data = result.model_dump()
        assert "formatted_text" not in data

    def test_include_formatted_text_true(self):
        with _patch_api():
            result = get_transcript("test-otid", include_formatted_text=True)
        assert len(result.segments) == 5
        data = result.model_dump()
        assert "formatted_text" in data
        assert "Alice" in data["formatted_text"]

    def test_negative_offset_returns_all(self):
        with _patch_api():
            result = get_transcript("test-otid", since_offset_ms=-100)
        assert len(result.segments) == 5

    def test_since_offset_with_max_segments(self):
        """Filter first, then truncate."""
        with _patch_api():
            result = get_transcript("test-otid", max_segments=2, since_offset_ms=5000)
        # After filtering: Third(10000), Fourth(20000), Fifth(30000)
        # After max_segments=2: Fourth(20000), Fifth(30000)
        assert len(result.segments) == 2
        assert result.segments[0].text == "Fourth"
        assert result.segments[1].text == "Fifth"

    def test_since_offset_exact_boundary(self):
        """Passing exact offset of a segment excludes it (strictly >)."""
        with _patch_api():
            result = get_transcript("test-otid", since_offset_ms=10000)
        # Excludes segments at 1000, 5000, 10000; keeps 20000 and 30000
        assert len(result.segments) == 2
        assert result.segments[0].text == "Fourth"


class TestGetTranscriptOutputFile:
    """#333: output_file writes the formatted transcript to disk and returns metadata only."""

    def test_writes_file_and_returns_metadata(self, tmp_path):
        out = tmp_path / "transcript.txt"
        with _patch_api():
            result = get_transcript("test-otid", output_file=str(out))

        # File contains the formatted transcript
        contents = out.read_text()
        assert "Alice" in contents
        assert "First" in contents
        assert "Fifth" in contents

        # Response is metadata-only (segments and formatted_text omitted from serialization)
        assert result.segment_count == 5
        assert result.output_file == str(out)
        assert result.speakers == ["Alice", "Bob"]

        data = result.model_dump()
        assert "formatted_text" not in data
        assert data["segments"] == []

    def test_expanduser(self, tmp_path, monkeypatch):
        """~/path is expanded to the real home directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        with _patch_api():
            result = get_transcript("test-otid", output_file="~/out.txt")
        expected = tmp_path / "out.txt"
        assert expected.exists()
        assert result.output_file == str(expected)

    def test_empty_output_file_uses_inline_response(self):
        """No output_file → existing inline behavior."""
        with _patch_api():
            result = get_transcript("test-otid", output_file="")
        assert len(result.segments) == 5
        assert result.formatted_text is not None
        assert result.output_file == ""

    def test_creates_missing_parent_dirs(self, tmp_path):
        """Nested parent directories are created automatically."""
        out = tmp_path / "subdir" / "deep" / "transcript.txt"
        with _patch_api():
            get_transcript("test-otid", output_file=str(out))
        assert out.exists()
        assert "Alice" in out.read_text()


class TestOtterToolDispatch:
    """Cover the MCP otter() tool dispatch — every action branch + arg validation."""

    def test_live_dispatches_to_find_live_meetings(self):
        from mcp_handley_lab.otter.tool import otter

        meetings = [MeetingSummary(otid="x", title="A", live_status="live")]
        with patch(
            "mcp_handley_lab.otter.shared.find_live_meetings", return_value=meetings
        ):
            result = otter(action="live")
        assert result.meetings == meetings

    def test_transcript_requires_otid(self):
        from mcp_handley_lab.otter.tool import otter

        try:
            otter(action="transcript", otid="")
        except ValueError as e:
            assert "otid" in str(e)
        else:
            raise AssertionError("Expected ValueError")

    def test_transcript_dispatches_with_output_file(self, tmp_path):
        from mcp_handley_lab.otter.tool import otter

        out = tmp_path / "t.txt"
        captured = {}

        def fake_get_transcript(*args, **kwargs):
            captured.update(kwargs)
            return TranscriptResult(
                otid=args[0],
                segment_count=0,
                speakers=[],
                output_file=str(out),
            )

        with patch(
            "mcp_handley_lab.otter.shared.get_transcript",
            side_effect=fake_get_transcript,
        ):
            result = otter(action="transcript", otid="abc", output_file=str(out))
        assert captured["output_file"] == str(out)
        assert result.transcript.output_file == str(out)

    def test_recent_dispatches_to_list_recent(self):
        from mcp_handley_lab.otter.tool import otter

        meetings = [MeetingSummary(otid="x", title="A")]
        with patch(
            "mcp_handley_lab.otter.shared.list_recent_meetings", return_value=meetings
        ):
            result = otter(action="recent", limit=5)
        assert result.meetings == meetings

    def test_search_requires_query(self):
        from mcp_handley_lab.otter.tool import otter

        try:
            otter(action="search", query="")
        except ValueError as e:
            assert "query" in str(e)
        else:
            raise AssertionError("Expected ValueError")

    def test_search_dispatches_to_search_meetings(self):
        from mcp_handley_lab.otter.tool import otter

        meetings = [MeetingSummary(otid="x", title="Match")]
        with patch(
            "mcp_handley_lab.otter.shared.search_meetings", return_value=meetings
        ):
            result = otter(action="search", query="match")
        assert result.meetings == meetings

    def test_refresh_dispatches_to_refresh_session(self):
        from mcp_handley_lab.otter.shared import RefreshResult
        from mcp_handley_lab.otter.tool import otter

        rr = RefreshResult(
            refreshed_at="2026-01-01T00:00:00Z", cookie_count=3, session_path="/tmp/s"
        )
        with patch("mcp_handley_lab.otter.shared.refresh_session", return_value=rr):
            result = otter(action="refresh")
        assert result.refresh == rr
