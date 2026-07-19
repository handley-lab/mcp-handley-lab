"""Unit tests for interactive terminal launching."""

from unittest.mock import MagicMock, patch

from mcp_handley_lab.common.terminal import (
    check_interactive_support,
    launch_interactive,
)


@patch("mcp_handley_lab.common.terminal.subprocess.Popen")
@patch("mcp_handley_lab.common.terminal.subprocess.run")
def test_uses_tmux_window_when_server_reachable(mock_run, mock_popen):
    # tmux list-sessions succeeds -> a server is reachable even without $TMUX.
    mock_run.return_value = MagicMock(returncode=0)

    result = launch_interactive("mutt -f inbox", window_title="Mutt")

    assert "tmux window" in result
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert ["tmux", "new-window", "-n", "Mutt", "mutt -f inbox"] in commands
    mock_popen.assert_not_called()


@patch("mcp_handley_lab.common.terminal.subprocess.Popen")
@patch("mcp_handley_lab.common.terminal.subprocess.run")
def test_falls_back_to_ghostty_without_tmux_server(mock_run, mock_popen):
    # tmux list-sessions fails -> no server -> ghostty GUI fallback.
    mock_run.return_value = MagicMock(returncode=1)

    result = launch_interactive("mutt -f inbox", window_title="Mutt")

    assert "ghostty" in result
    mock_popen.assert_called_once_with(
        [
            "ghostty",
            "--gtk-single-instance=false",
            "--title=Mutt",
            "-e",
            "sh",
            "-c",
            "mutt -f inbox",
        ]
    )


@patch("mcp_handley_lab.common.terminal.subprocess.run")
def test_check_interactive_support_reports_ghostty_not_xterm(mock_run):
    mock_run.return_value = MagicMock(returncode=0)

    result = check_interactive_support()

    assert "ghostty_available" in result
    assert "xterm_available" not in result
