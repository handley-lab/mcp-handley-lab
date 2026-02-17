"""Unit tests for Otter.ai transcript formatting and parsing logic."""

from mcp_handley_lab.otter.shared import (
    MeetingSummary,
    OtterResult,
    _format_transcript,
    _parse_meeting,
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
