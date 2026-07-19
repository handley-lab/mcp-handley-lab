"""Tests for messenger command parsing and handling."""

import asyncio
from unittest.mock import patch

import pytest

from mcp_handley_lab.messenger.server import (
    ChatActor,
    IncomingEvent,
    WebhookHandler,
    _context_footer,
    _dispatch,
    _extract_usage,
    _get_or_create_actor,
    _parse_command,
)


def test_webhook_log_omits_query_string(capsys):
    handler = WebhookHandler.__new__(WebhookHandler)
    handler.client_address = ("127.0.0.1", 1234)
    handler.log_message(
        '"%s" %s %s',
        "GET /webhook?hub.verify_token=secret HTTP/1.1",
        "200",
        "-",
    )
    output = capsys.readouterr().out
    assert '"GET /webhook HTTP/1.1" 200 -' in output
    assert "secret" not in output


# ---------------------------------------------------------------------------
# _parse_command tests
# ---------------------------------------------------------------------------


class TestParseCommand:
    def test_basic_reset(self):
        assert _parse_command("/reset") == ("/reset", "")

    def test_with_args(self):
        assert _parse_command("/model opus") == ("/model", "opus")

    def test_args_with_at(self):
        assert _parse_command("/model foo@bar") == ("/model", "foo@bar")

    def test_telegram_botname(self):
        assert _parse_command("/reset@MyBot") == ("/reset", "")

    def test_telegram_botname_with_args(self):
        assert _parse_command("/model@MyBot opus") == ("/model", "opus")

    def test_unknown_command(self):
        assert _parse_command("/random") is None

    def test_not_slash(self):
        assert _parse_command("hello") is None

    def test_path_not_command(self):
        assert _parse_command("/home/user/file") is None

    def test_all_commands(self):
        for cmd in (
            "/reset",
            "/cancel",
            "/model",
            "/help",
            "/status",
        ):
            assert _parse_command(cmd) is not None

    def test_whitespace_padding(self):
        assert _parse_command("  /reset  ") == ("/reset", "")

    def test_case_insensitive(self):
        assert _parse_command("/RESET") == ("/reset", "")

    def test_empty_string(self):
        assert _parse_command("") is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockPlatform:
    """Mock platform that records send_text calls."""

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_text(self, conversation_id, text, reply_to=None):
        self.sent.append((conversation_id, text))
        return "msg-id"

    def send_media(self, conversation_id, path, caption="", reply_to=None):
        return None

    def send_typing(self, conversation_id):
        pass


def _make_event(text: str, platform=None, conversation_id="test:123") -> IncomingEvent:
    plat = platform or MockPlatform()
    parsed = _parse_command(text)
    kind = "command" if parsed is not None else "text"
    return IncomingEvent(
        conversation_id=conversation_id,
        kind=kind,
        text=text,
        platform=plat,
        message_id="ev-1",
    )


def _make_actor(platform=None, conversation_id="test:123", tmp_path=None):
    plat = platform or MockPlatform()
    actor = ChatActor(conversation_id, plat)
    if tmp_path:
        actor.cwd = tmp_path
        actor._state_file = tmp_path / "loop_state.json"
        actor._msg_log_file = tmp_path / "message_log.json"
    return actor


# ---------------------------------------------------------------------------
# ChatActor command tests
# ---------------------------------------------------------------------------


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_help_sends_text(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        event = _make_event("/help", platform)
        await actor._handle(event)
        assert len(platform.sent) == 1
        text = platform.sent[0][1]
        assert "/reset" in text
        assert "/help" in text


class TestResetCommand:
    @pytest.mark.asyncio
    async def test_reset_is_explicitly_unavailable(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.alan_addr = "claude-123"
        await actor._handle(_make_event("/reset", platform))
        assert actor.alan_addr == "claude-123"
        assert "not yet supported" in platform.sent[0][1].lower()


class TestInterruptCommands:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("cmd", ["/reset", "/cancel"])
    async def test_dispatch_interrupts_running_actor(self, cmd):
        import mcp_handley_lab.messenger.server as srv

        old_actors = srv._actors
        old_loop = srv._loop

        try:
            srv._loop = asyncio.new_event_loop()
            srv._actors = {}

            platform = MockPlatform()
            conv_id = "test:interrupt"

            actor = _get_or_create_actor(conv_id, platform)
            actor.alan_addr = "claude-stuck"

            event = _make_event(cmd, platform, conversation_id=conv_id)
            with patch(
                "mcp_handley_lab.messenger.server.alan.interrupt"
            ) as mock_interrupt:
                await _dispatch(event)
                mock_interrupt.assert_called_once_with("claude-stuck")

            assert not actor.queue.empty()
        finally:
            srv._loop.close()
            srv._actors = old_actors
            srv._loop = old_loop

    @pytest.mark.asyncio
    async def test_dispatch_no_interrupt_without_actor(self):
        import mcp_handley_lab.messenger.server as srv

        old_actors = srv._actors
        old_loop = srv._loop

        try:
            srv._loop = asyncio.new_event_loop()
            srv._actors = {}

            platform = MockPlatform()
            conv_id = "test:noop"

            event = _make_event("/reset", platform, conversation_id=conv_id)
            with patch(
                "mcp_handley_lab.messenger.server.alan.interrupt"
            ) as mock_interrupt:
                await _dispatch(event)
                mock_interrupt.assert_not_called()
        finally:
            srv._loop.close()
            srv._actors = old_actors
            srv._loop = old_loop


class TestCancelCommand:
    @pytest.mark.asyncio
    async def test_cancel_sends_confirmation(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.alan_addr = "claude-123"

        event = _make_event("/cancel", platform)
        await actor._handle(event)

        assert "cancelled" in platform.sent[0][1].lower()
        assert actor.alan_addr == "claude-123"
        assert not actor._stopped  # actor still running


class TestModelCommand:
    @pytest.mark.asyncio
    async def test_model_set(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.cwd.mkdir(parents=True, exist_ok=True)

        event = _make_event("/model opus", platform)
        await actor._handle(event)

        assert actor._model == ""
        assert "not yet supported" in platform.sent[0][1].lower()

    @pytest.mark.asyncio
    async def test_model_query(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor._model = "sonnet"

        event = _make_event("/model", platform)
        await actor._handle(event)

        assert "sonnet" in platform.sent[0][1].lower()

    @pytest.mark.asyncio
    async def test_model_query_default(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)

        event = _make_event("/model", platform)
        await actor._handle(event)

        assert "default" in platform.sent[0][1].lower()

    @pytest.mark.asyncio
    async def test_model_does_not_mutate_active_actor(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.alan_addr = "claude-123"
        await actor._handle(_make_event("/model opus", platform))
        assert actor.alan_addr == "claude-123"
        assert actor._model == ""


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_status_active(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.alan_addr = "claude-123"

        with patch(
            "mcp_handley_lab.messenger.server.alan.status",
            return_value={
                "addr": "claude-123",
                "state": "working",
                "native": {"id": "sess-abc"},
            },
        ):
            event = _make_event("/status", platform)
            await actor._handle(event)

        text = platform.sent[0][1]
        assert "working" in text.lower()
        assert "sess-abc" in text

    @pytest.mark.asyncio
    async def test_status_no_session(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)

        event = _make_event("/status", platform)
        await actor._handle(event)

        assert "no active session" in platform.sent[0][1].lower()

    @pytest.mark.asyncio
    async def test_status_reports_inactive_actor(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.alan_addr = "claude-dead"
        actor.cwd.mkdir(parents=True, exist_ok=True)

        with patch(
            "mcp_handley_lab.messenger.server.alan.status",
            return_value=None,
        ):
            event = _make_event("/status", platform)
            await actor._handle(event)

        assert actor.alan_addr == "claude-dead"
        assert "inactive" in platform.sent[0][1].lower()


class TestActorLifecycle:
    def test_stopped_actor_replaced(self, tmp_path):
        """_get_or_create_actor replaces a stopped actor."""
        import mcp_handley_lab.messenger.server as srv

        old_actors = srv._actors
        old_loop = srv._loop

        try:
            srv._loop = asyncio.new_event_loop()
            srv._actors = {}

            platform = MockPlatform()
            conv_id = "test:lifecycle"

            # Create initial actor
            actor1 = _get_or_create_actor(conv_id, platform)
            assert conv_id in srv._actors

            # Mark it as stopped
            actor1._stopped = True

            # Should create a new actor
            actor2 = _get_or_create_actor(conv_id, platform)
            assert actor2 is not actor1
            assert not actor2._stopped
        finally:
            srv._loop.close()
            srv._actors = old_actors
            srv._loop = old_loop


class TestAlanQuery:
    def test_query_uses_stable_actor_and_passive_identity(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, "telegram:-123:7", tmp_path)
        actor.cwd.mkdir(parents=True, exist_ok=True)

        with (
            patch(
                "mcp_handley_lab.messenger.server.alan.ensure_claude",
                return_value="claude-test",
            ) as ensure,
            patch(
                "mcp_handley_lab.messenger.server.alan.query",
                return_value="response",
            ) as query,
        ):
            result = actor._query("hello", "telegram-message-1")

        assert result == "response"
        ensure.assert_called_once_with(None, "msg-telegram:-123:7", str(tmp_path))
        query.assert_called_once_with(
            "claude-test",
            actor.passive_addr,
            "hello",
            "telegram-message-1",
        )


class TestStatePersistence:
    def test_save_load_with_model(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.alan_addr = "claude-123"
        actor._model = "opus"
        actor.cwd.mkdir(parents=True, exist_ok=True)
        actor._save_state()

        actor2 = _make_actor(platform, tmp_path=tmp_path)
        actor2._load_state()
        assert actor2.alan_addr == "claude-123"
        assert actor2._model == "opus"

    def test_old_loop_state_is_not_adopted(self, tmp_path):
        import json

        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        state_file = tmp_path / "loop_state.json"
        state_file.write_text(
            json.dumps({"loop_id": "claude-old", "session_id": "sess-old"})
        )
        actor._load_state()
        assert actor.alan_addr is None
        assert actor._model == ""


# ---------------------------------------------------------------------------
# _extract_usage / _context_footer tests
# ---------------------------------------------------------------------------

_RESULT_EVENT = {
    "type": "result",
    "total_cost_usd": 0.05,
    "modelUsage": {
        "claude-opus-4-6": {
            "contextWindow": 200000,
            "inputTokens": 80000,
            "outputTokens": 20000,
            "cacheCreationInputTokens": 5000,
            "cacheReadInputTokens": 3000,
            "costUSD": 0.05,
        },
    },
}


class TestExtractUsage:
    def test_extracts_from_last_cell(self):
        cells = [
            {"index": 0, "events": []},
            {"index": 1, "events": [{"type": "assistant"}, _RESULT_EVENT]},
        ]
        usage = _extract_usage(cells)
        assert usage is not None
        assert usage["context_window"] == 200000
        assert usage["input_tokens"] == 80000
        assert usage["output_tokens"] == 20000
        assert "cost_usd" not in usage

    def test_empty_cells(self):
        assert _extract_usage([]) is None

    def test_no_result_event(self):
        cells = [{"index": 0, "events": [{"type": "assistant"}]}]
        assert _extract_usage(cells) is None

    def test_no_events_key(self):
        cells = [{"index": 0}]
        assert _extract_usage(cells) is None


class TestContextFooter:
    def test_basic_footer(self):
        usage = {
            "context_window": 200000,
            "input_tokens": 80000,
            "output_tokens": 20000,
        }
        assert _context_footer(usage) == "50% context"

    def test_zero_context_window(self):
        usage = {
            "context_window": 0,
            "input_tokens": 0,
            "output_tokens": 0,
        }
        assert _context_footer(usage) == ""


class TestAlanResponse:
    @pytest.mark.asyncio
    async def test_response_comes_from_causally_correlated_query(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor.cwd.mkdir(parents=True, exist_ok=True)

        event = _make_event("hello", platform)
        event.kind = "text"

        with patch.object(actor, "_query", return_value="Hello there!") as query:
            await actor._handle(event)

        text = platform.sent[0][1]
        assert "Hello there!" in text
        query.assert_called_once_with("hello", "ev-1")

    @pytest.mark.asyncio
    async def test_duplicate_platform_message_is_not_submitted_twice(self, tmp_path):
        platform = MockPlatform()
        actor = _make_actor(platform, tmp_path=tmp_path)
        actor._message_log["ev-1"] = {
            "role": "user",
            "text": "hello",
            "completed": True,
        }
        with patch.object(actor, "_query") as query:
            await actor._handle(_make_event("hello", platform))
        query.assert_not_called()
