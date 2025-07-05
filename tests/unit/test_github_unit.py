"""Unit tests for GitHub CI Monitor tool."""

import json
from unittest.mock import patch

import pytest
from mcp_handley_lab.github.tool import (
    monitor_pr_checks,
    server_info,
)


class TestGitHubCIMonitor:
    """Test GitHub CI Monitor functionality."""

    @patch("mcp_handley_lab.github.tool.run_command")
    def test_server_info_success(self, mock_run_command):
        """Test server info success."""
        mock_run_command.side_effect = [
            (b"gh version 2.32.1 (2023-07-25)", b""),
            (b"github.com\n  \xe2\x9c\x93 Logged in to github.com", b""),
        ]

        result = server_info()

        assert "Status: Connected and ready" in result
        assert "GitHub CLI Version: gh" in result
        assert "Authentication: github.com" in result

    @patch("mcp_handley_lab.github.tool.run_command")
    def test_server_info_not_found(self, mock_run_command):
        """Test server info when gh not found."""
        mock_run_command.side_effect = FileNotFoundError("command not found")

        with pytest.raises(FileNotFoundError):
            server_info()

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool.run_command")
    def test_monitor_pr_checks_all_passed(
        self, mock_run_command, mock_time, mock_sleep
    ):
        """Test monitoring with all checks passed."""
        mock_time.side_effect = [0, 10]  # Start time, first check
        test_data = [
            {"name": "build", "state": "SUCCESS"},
            {"name": "test", "state": "SUCCESS"},
        ]
        mock_run_command.return_value = (json.dumps(test_data).encode(), b"")

        result = monitor_pr_checks(25)

        assert "2/2 passed, 0 failed, 0 pending" in result
        assert "All checks passed! Ready to merge" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool.run_command")
    def test_monitor_pr_checks_failed_check(
        self, mock_run_command, mock_time, mock_sleep
    ):
        """Test monitoring with failed check."""
        mock_time.side_effect = [0, 10]  # Start time, first check
        test_data = [
            {"name": "build", "state": "SUCCESS"},
            {"name": "test", "state": "FAILURE"},
        ]
        mock_run_command.return_value = (json.dumps(test_data).encode(), b"")

        result = monitor_pr_checks(25)

        assert "1/2 passed, 1 failed, 0 pending" in result
        assert "1 check(s) failed - monitoring stopped" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool.run_command")
    def test_monitor_pr_checks_pending_then_timeout(
        self, mock_run_command, mock_time, mock_sleep
    ):
        """Test monitoring with pending checks that timeout."""
        mock_time.side_effect = [0, 10, 35, 65, 70]
        test_data = [{"name": "test", "state": "PENDING"}]
        mock_run_command.return_value = (json.dumps(test_data).encode(), b"")

        result = monitor_pr_checks(25, timeout_minutes=1)

        assert "0/1 passed, 0 failed, 1 pending" in result
        assert "Waiting for 1 pending check(s)" in result
        assert "Monitoring timed out after 1 minutes" in result

    def test_monitor_pr_checks_invalid_parameters(self):
        """Test invalid parameters for monitor_pr_checks."""
        with pytest.raises(
            ValueError,
            match="timeout_minutes and check_interval_seconds must be positive",
        ):
            monitor_pr_checks(25, timeout_minutes=-1)

        with pytest.raises(
            ValueError,
            match="timeout_minutes and check_interval_seconds must be positive",
        ):
            monitor_pr_checks(25, check_interval_seconds=-1)

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool.run_command")
    def test_monitor_pr_checks_no_checks(self, mock_run_command, mock_time, mock_sleep):
        """Test monitoring when no checks exist."""
        mock_time.side_effect = [0, 10, 35, 65, 70]
        mock_run_command.return_value = (b"[]", b"")

        result = monitor_pr_checks(25, timeout_minutes=1)

        assert "No checks found for this PR" in result
        assert "Monitoring timed out" in result

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool.run_command")
    def test_monitor_pr_checks_json_parse_error(
        self, mock_run_command, mock_time, mock_sleep
    ):
        """Test monitoring with JSON parse error - should fail fast."""
        mock_time.side_effect = [0, 10]
        mock_run_command.return_value = (b"invalid json", b"")

        with pytest.raises(json.JSONDecodeError):
            monitor_pr_checks(25, timeout_minutes=1)

    @patch("time.sleep")
    @patch("time.time")
    @patch("mcp_handley_lab.github.tool.run_command")
    def test_monitor_pr_checks_custom_timing(
        self, mock_run_command, mock_time, mock_sleep
    ):
        """Test monitoring with custom timing parameters."""
        mock_time.side_effect = [0, 5]
        test_data = [{"name": "test", "state": "SUCCESS"}]
        mock_run_command.return_value = (json.dumps(test_data).encode(), b"")

        result = monitor_pr_checks(42, timeout_minutes=2, check_interval_seconds=5)

        assert "Starting CI monitoring for PR #42" in result
        assert "Timeout: 2 minutes" in result
        assert "Check interval: 5 seconds" in result
        assert "All checks passed" in result


class TestGitHubCIMonitorErrorHandling:
    """Test error handling for GitHub CI Monitor."""

    def test_run_command_error_propagation(self):
        """Test that run_command errors propagate naturally."""
        # Since we removed _run_gh_command, errors from run_command should propagate
        # This tests the fail-fast philosophy - we don't catch and re-wrap errors

        with patch("mcp_handley_lab.github.tool.run_command") as mock_run:
            mock_run.side_effect = RuntimeError("Command failed")

            with pytest.raises(RuntimeError, match="Command failed"):
                server_info()

    @patch("mcp_handley_lab.github.tool.run_command")
    def test_server_info_auth_error_propagation(self, mock_run_command):
        """Test that auth errors propagate naturally."""
        # First call (version) succeeds, second call (auth) fails
        mock_run_command.side_effect = [
            (b"gh version 2.32.1", b""),
            RuntimeError("Authentication failed"),
        ]

        with pytest.raises(RuntimeError, match="Authentication failed"):
            server_info()
