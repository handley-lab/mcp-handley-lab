"""Google Calendar test fixtures and utilities."""
from collections.abc import AsyncGenerator, Callable
from typing import Any

import pytest


@pytest.fixture
async def event_creator(
    google_calendar_test_config,
) -> AsyncGenerator[Callable[[dict[str, Any]], str], None]:
    """
    A factory fixture that creates Google Calendar events and guarantees
    they are deleted after the test run.

    Usage in tests:
        async def test_something(event_creator):
            event_id = await event_creator({
                "summary": "Test Event",
                "start_datetime": "tomorrow at 10am",
                "end_datetime": "tomorrow at 11am"
            })
            # Use event_id in test...
            # Event will be automatically cleaned up
    """
    from mcp_handley_lab.google_calendar.tool import mcp

    created_event_ids = []

    async def _event_factory(params: dict[str, Any]) -> str:
        """The factory function that tests will call."""
        nonlocal created_event_ids

        # Ensure required parameters have defaults
        default_params = {
            "calendar_id": "primary",
            "location": "",
            "attendees": [],
            "start_timezone": "",
            "end_timezone": "",
        }

        # Merge user params with defaults
        full_params = {**default_params, **params}

        result = await mcp.call_tool("create_event", full_params)
        # mcp.call_tool returns a list with TextContent - need to parse the JSON
        import json

        response = json.loads(result[0].text)
        assert (
            "error" not in response
        ), f"Failed to create event: {response.get('error')}"

        event_id = response.get("event_id")
        assert event_id, f"No event_id in response: {response}"

        created_event_ids.append(event_id)
        return event_id

    yield _event_factory  # Provide the factory to the test

    # --- Teardown Logic ---
    print(f"\nCleaning up {len(created_event_ids)} test event(s)...")
    for event_id in created_event_ids:
        try:
            await mcp.call_tool(
                "delete_event", {"event_id": event_id, "calendar_id": "primary"}
            )
        except Exception as e:
            print(f"  - Warning: Failed to delete event {event_id}: {e}")
