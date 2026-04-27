"""Unit tests for Google Calendar send_updates plumbing (#334) and the
unknown-parameter validator (#313).

These tests use mocked Google Calendar service objects so they run without
network or credentials.
"""

from unittest.mock import MagicMock

import pytest

from mcp_handley_lab.google_calendar import shared
from mcp_handley_lab.google_calendar.tool import mcp


def _build_fake_service(returned_event: dict | None = None) -> MagicMock:
    """Construct a Mock that mimics the chained Google Calendar service API.

    Stubs the methods touched by `shared.create` and `shared.update` along
    the patch + move paths: events().{insert,patch,move,get}(...).execute(),
    and calendars().get(...).execute() (used by _get_calendar_timezone).
    """
    service = MagicMock()
    event_payload = returned_event or {
        "id": "evt-id",
        "summary": "Test",
        "start": {"dateTime": "2026-05-01T10:00:00Z", "timeZone": "UTC"},
        "end": {"dateTime": "2026-05-01T11:00:00Z", "timeZone": "UTC"},
        "attendees": [],
        "htmlLink": "https://calendar.google.com/event?eid=evt-id",
    }
    service.events.return_value.insert.return_value.execute.return_value = event_payload
    service.events.return_value.patch.return_value.execute.return_value = event_payload
    service.events.return_value.move.return_value.execute.return_value = event_payload
    service.events.return_value.get.return_value.execute.return_value = event_payload
    service.calendars.return_value.get.return_value.execute.return_value = {
        "timeZone": "UTC"
    }
    return service


@pytest.fixture
def fake_service(monkeypatch):
    service = _build_fake_service()
    monkeypatch.setattr(shared, "_get_calendar_service", lambda: service)
    return service


class TestCreateSendUpdates:
    """#334: shared.create must thread send_updates to events().insert()."""

    def test_default_is_none(self, fake_service):
        shared.create(
            summary="Test",
            start_datetime="2026-05-01T10:00:00Z",
            end_datetime="2026-05-01T11:00:00Z",
            calendar_id="primary",
        )
        kwargs = fake_service.events.return_value.insert.call_args.kwargs
        assert kwargs["sendUpdates"] == "none"

    @pytest.mark.parametrize("value", ["all", "externalOnly", "none"])
    def test_override_flows_through(self, fake_service, value):
        shared.create(
            summary="Test",
            start_datetime="2026-05-01T10:00:00Z",
            end_datetime="2026-05-01T11:00:00Z",
            calendar_id="primary",
            send_updates=value,
        )
        kwargs = fake_service.events.return_value.insert.call_args.kwargs
        assert kwargs["sendUpdates"] == value


class TestUpdatePatchSendUpdates:
    """#334: shared.update patch path must thread send_updates to events().patch()."""

    def test_default_is_none(self, fake_service):
        shared.update(
            event_id="evt-id",
            calendar_id="primary",
            summary="New title",
        )
        kwargs = fake_service.events.return_value.patch.call_args.kwargs
        assert kwargs["sendUpdates"] == "none"

    @pytest.mark.parametrize("value", ["all", "externalOnly"])
    def test_override_flows_through(self, fake_service, value):
        shared.update(
            event_id="evt-id",
            calendar_id="primary",
            summary="New title",
            send_updates=value,
        )
        kwargs = fake_service.events.return_value.patch.call_args.kwargs
        assert kwargs["sendUpdates"] == value


class TestUpdateMoveSendUpdates:
    """#334: shared.update move path must thread send_updates to events().move()."""

    def test_default_is_none(self, fake_service):
        shared.update(
            event_id="evt-id",
            calendar_id="primary",
            destination_calendar_id="other@group.calendar.google.com",
        )
        kwargs = fake_service.events.return_value.move.call_args.kwargs
        assert kwargs["sendUpdates"] == "none"

    def test_override_flows_through(self, fake_service):
        shared.update(
            event_id="evt-id",
            calendar_id="primary",
            destination_calendar_id="other@group.calendar.google.com",
            send_updates="all",
        )
        kwargs = fake_service.events.return_value.move.call_args.kwargs
        assert kwargs["sendUpdates"] == "all"


class TestUnknownParameterValidator:
    """#313: _validating_call_tool must raise on unknown parameters."""

    @pytest.mark.asyncio
    async def test_rejects_unknown_params(self):
        # Verbatim from the issue body — these are invalid: the real names
        # are start_date / end_date / calendar_id, and there is no `op`.
        with pytest.raises(ValueError, match="Unknown parameter"):
            await mcp.call_tool(
                "read",
                {
                    "op": "list_events",
                    "date": "2026-02-20",
                    "calendar": "Research",
                },
            )
